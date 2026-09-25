from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependency import CurrentUser, bearer_scheme
from app.auth.utils import create_session_token, hash_password, hash_session_token, verify_password
from app.config import settings
from app.core.database import get_session
from app.entities.models import Session, User
from app.entities.users.schemas import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    email = payload.email.lower()
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(email=email, password_hash=hash_password(payload.password.get_secret_value()))
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    token = create_session_token()
    db_session = Session(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.session_lifetime_days),
    )
    session.add(db_session)
    await session.commit()
    return TokenResponse(token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password.get_secret_value(), user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_session_token()
    session.add(
        Session(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.session_lifetime_days),
        )
    )
    await session.commit()
    return TokenResponse(token=token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: CurrentUser,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    if credentials is not None:
        await session.execute(
            delete(Session).where(
                Session.user_id == current_user.id,
                Session.token_hash == hash_session_token(credentials.credentials),
            )
        )
    await session.commit()
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserPublic)
async def me(current_user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(current_user)
