import logging
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.utils import create_session_token, hash_password, hash_session_token
from app.config import settings
from app.entities.models import EmailVerification, Session, User, utc_now
from app.notifications.mail import MailUnavailable, send_verification_email


logger = logging.getLogger("api_sandbox.email_verification")


async def issue_session(session: AsyncSession, user: User) -> str:
    token = create_session_token()
    session.add(Session(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=utc_now() + timedelta(days=settings.session_lifetime_days),
    ))
    await session.commit()
    return token


async def request_verification(session: AsyncSession, email: str) -> None:
    user_query = select(User.id).where(User.email == email)
    if await session.scalar(user_query) is not None:
        raise HTTPException(409, "EMAIL_ALREADY_REGISTERED")

    token = create_session_token()
    now = utc_now()
    cooldown = settings.email_verification_resend_seconds
    values = {
        "token_hash": hash_session_token(token),
        "expires_at": now + timedelta(minutes=settings.email_verification_ttl_minutes),
        "resend_at": now + timedelta(seconds=cooldown),
    }
    reserved = await session.scalar(
        update(EmailVerification)
        .where(EmailVerification.email == email, EmailVerification.resend_at <= now)
        .values(**values)
        .returning(EmailVerification.email)
    )
    if reserved is None:
        session.add(EmailVerification(email=email, **values))
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                429,
                {"code": "EMAIL_VERIFICATION_COOLDOWN", "retry_after_seconds": cooldown},
                headers={"Retry-After": str(cooldown)},
            ) from exc

    # Check again after acquiring the pending row, in case verification won the race.
    if await session.scalar(user_query) is not None:
        await session.rollback()
        raise HTTPException(409, "EMAIL_ALREADY_REGISTERED")

    try:
        await send_verification_email(email, token)
    except MailUnavailable:
        await session.rollback()
        logger.warning("Email verification delivery failed")
        raise HTTPException(503, "EMAIL_DELIVERY_UNAVAILABLE") from None
    await session.commit()


async def verify_registration(session: AsyncSession, token: str, password: str) -> str:
    email = await session.scalar(
        delete(EmailVerification)
        .where(
            EmailVerification.token_hash == hash_session_token(token),
            EmailVerification.expires_at > utc_now(),
        )
        .returning(EmailVerification.email)
    )
    if email is None:
        raise HTTPException(400, "EMAIL_VERIFICATION_INVALID")

    user = User(email=email, password_hash=await run_in_threadpool(hash_password, password))
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "EMAIL_ALREADY_REGISTERED") from exc
    return await issue_session(session, user)
