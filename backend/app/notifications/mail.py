import asyncio
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urlsplit

import aiosmtplib

from app.config import settings


class MailUnavailable(Exception):
    pass


def verification_url(token: str) -> str:
    base = settings.frontend_public_url.strip()
    parsed = urlsplit(base)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.query
        or parsed.fragment
        or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"})
    ):
        raise MailUnavailable
    return f"{base}#verify-email={token}"


def verification_message(recipient: str, url: str) -> EmailMessage:
    minutes = settings.email_verification_ttl_minutes
    template_path = Path(__file__).with_name("templates") / "verify_email.html"
    html = Template(template_path.read_text(encoding="utf-8")).substitute(
        verification_url=escape(url, quote=True),
        ttl_minutes=str(minutes),
    )
    message = EmailMessage()
    message["From"] = formataddr(("API Sandbox", settings.smtp_username))
    message["To"] = recipient
    message["Subject"] = "Подтвердите почту для API Sandbox"
    message.set_content(
        f"Откройте ссылку и задайте пароль для API Sandbox:\n{url}\n\n"
        f"Ссылка действует {minutes} мин. "
        "Если вы не запрашивали регистрацию, проигнорируйте это письмо."
    )
    message.add_alternative(html, subtype="html")
    return message


async def send_verification_email(recipient: str, token: str) -> None:
    password = settings.smtp_password.get_secret_value()
    if not settings.smtp_username or not password:
        raise MailUnavailable
    try:
        message = verification_message(recipient, verification_url(token))
        async with asyncio.timeout(settings.smtp_timeout_seconds):
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_hostname,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=password,
                use_tls=True,
                timeout=settings.smtp_timeout_seconds,
            )
    except (aiosmtplib.SMTPException, OSError, ValueError) as exc:
        raise MailUnavailable from exc
