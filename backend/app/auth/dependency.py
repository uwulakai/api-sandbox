from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import hash_session_token
from app.core.database import get_session
from app.entities.models import Session, User


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.execute(
        select(Session, User)
        .join(User, User.id == Session.user_id)
        .where(
            Session.token_hash == hash_session_token(credentials.credentials),
            Session.expires_at > datetime.now(timezone.utc),
            User.is_active.is_(True),
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db_session, user = row
    db_session.last_seen_at = datetime.now(timezone.utc)
    await session.commit()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
