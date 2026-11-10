from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr
from sqlalchemy import select, update

from app.config import settings
from app.entities.models import EmailVerification, utc_now
from app.entities.users import verification
from app.notifications import mail


EMAIL = "user@example.com"
PASSWORD = "password123"
REGISTER = "/api/v1/auth/register"
VERIFY = "/api/v1/auth/verify-email"
LOGIN = "/api/v1/auth/login"


async def test_registration_requires_single_use_email_token(client, sent_verifications, database):
    pending = await client.post(REGISTER, json={"email": EMAIL.upper()})
    assert pending.status_code == 202
    assert pending.json() == {
        "status": "verification_required",
        "resend_after_seconds": settings.email_verification_resend_seconds,
    }
    credentials = {"email": EMAIL, "password": PASSWORD}
    assert (await client.post(LOGIN, json=credentials)).status_code == 401

    token = sent_verifications[EMAIL]
    async with database() as session:
        stored = await session.scalar(select(EmailVerification))
        assert stored.token_hash == verification.hash_session_token(token)
        assert stored.token_hash != token

    cooldown = await client.post(REGISTER, json={"email": EMAIL})
    assert cooldown.status_code == 429
    seconds = settings.email_verification_resend_seconds
    assert cooldown.headers["Retry-After"] == str(seconds)
    assert cooldown.json()["detail"] == {
        "code": "EMAIL_VERIFICATION_COOLDOWN", "retry_after_seconds": seconds,
    }
    assert sent_verifications[EMAIL] == token

    invalid_password = "я" * 37
    invalid = await client.post(VERIFY, json={"token": token, "password": invalid_password})
    assert invalid.status_code == 422
    assert token not in invalid.text and invalid_password not in invalid.text
    assert "input" not in invalid.json()["detail"][0]

    proof = {"token": token, "password": PASSWORD}
    verified = await client.post(VERIFY, json=proof)
    assert verified.status_code == 200
    bearer = verified.json()["token"]
    assert bearer != token
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bearer}"})
    assert me.status_code == 200 and me.json()["email"] == EMAIL
    assert (await client.post(VERIFY, json=proof)).status_code == 400
    assert (await client.post(REGISTER, json={"email": EMAIL})).status_code == 409
    assert (await client.post(LOGIN, json=credentials)).status_code == 200


async def test_resend_replaces_token_only_after_successful_smtp(client, sent_verifications, database, monkeypatch):
    assert (await client.post(REGISTER, json={"email": EMAIL})).status_code == 202
    first = sent_verifications[EMAIL]
    async with database() as session:
        await session.execute(update(EmailVerification).values(resend_at=utc_now() - timedelta(seconds=1)))
        await session.commit()

    with monkeypatch.context() as smtp_failure:
        smtp_failure.setattr(verification, "send_verification_email", AsyncMock(side_effect=mail.MailUnavailable))
        unavailable = await client.post(REGISTER, json={"email": EMAIL})
        assert unavailable.status_code == 503
        assert unavailable.json()["detail"] == "EMAIL_DELIVERY_UNAVAILABLE"

    async with database() as session:
        stored = await session.scalar(select(EmailVerification))
        assert stored.token_hash == verification.hash_session_token(first)

    assert (await client.post(REGISTER, json={"email": EMAIL})).status_code == 202
    second = sent_verifications[EMAIL]
    assert second != first
    assert (await client.post(VERIFY, json={"token": first, "password": PASSWORD})).status_code == 400

    async with database() as session:
        await session.execute(update(EmailVerification).values(expires_at=utc_now() - timedelta(seconds=1)))
        await session.commit()
    assert (await client.post(VERIFY, json={"token": second, "password": PASSWORD})).status_code == 400


async def test_yandex_message_has_plain_text_and_html(monkeypatch):
    monkeypatch.setattr(settings, "frontend_public_url", "https://sandbox.example.com/")
    monkeypatch.setattr(settings, "smtp_username", "sender@yandex.com")
    monkeypatch.setattr(settings, "smtp_password", SecretStr("test-app-password"))
    send = AsyncMock()
    monkeypatch.setattr(mail.aiosmtplib, "send", send)
    await mail.send_verification_email(EMAIL, "verification-test-token")
    args, kwargs = send.call_args
    message, = args
    assert kwargs["use_tls"] is True
    assert kwargs["hostname"] == settings.smtp_hostname and kwargs["port"] == settings.smtp_port
    assert kwargs["username"] == "sender@yandex.com"
    assert message["To"] == EMAIL and "sender@yandex.com" in message["From"]
    url = "https://sandbox.example.com/#verify-email=verification-test-token"
    assert url in message.get_body(("plain",)).get_content()
    assert f'href="{url}"' in message.get_body(("html",)).get_content()
