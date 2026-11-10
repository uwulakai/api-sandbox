from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.dependency import CurrentUser, bearer_scheme
from app.auth.utils import hash_session_token, verify_password
from app.config import settings
from app.core.database import get_session
from app.entities.models import Session, User
from app.entities.users.schemas import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RegistrationPending,
    TokenResponse,
    UserPublic,
    VerifyEmailRequest,
)
from app.entities.users.verification import issue_session, request_verification, verify_registration


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegistrationPending,
    status_code=status.HTTP_202_ACCEPTED,
    responses={409: {"description": "Email already registered"},
               429: {"description": "Resend cooldown"}, 503: {"description": "Mail unavailable"}},
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> RegistrationPending:
    await request_verification(session, payload.email.lower())
    return RegistrationPending(resend_after_seconds=settings.email_verification_resend_seconds)


@router.post(
    "/verify-email", response_model=TokenResponse,
    responses={400: {"description": "Invalid, expired or used link"},
               409: {"description": "Email already registered"}},
)
async def verify_email(
    payload: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    token = await verify_registration(
        session, payload.token.get_secret_value(), payload.password.get_secret_value(),
    )
    return TokenResponse(token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not user.is_active or not await run_in_threadpool(
        verify_password, payload.password.get_secret_value(), user.password_hash,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(token=await issue_session(session, user))


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
