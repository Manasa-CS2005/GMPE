import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

import httpx


LOGGER = logging.getLogger(__name__)


def email_delivery_configured() -> bool:
    mode = os.getenv("LIFELOG_EMAIL_BACKEND", "").strip().lower()
    if not mode:
        mode = "smtp" if os.getenv("LIFELOG_SMTP_HOST", "").strip() else "console"
    sender = os.getenv("LIFELOG_SMTP_FROM_EMAIL", "").strip()
    if mode == "brevo":
        return bool(os.getenv("LIFELOG_BREVO_API_KEY", "").strip() and sender)
    if mode == "smtp":
        username = os.getenv("LIFELOG_SMTP_USERNAME", "").strip()
        password = os.getenv("LIFELOG_SMTP_PASSWORD", "")
        try:
            port = int(os.getenv("LIFELOG_SMTP_PORT", "587"))
        except ValueError:
            return False
        return bool(
            os.getenv("LIFELOG_SMTP_HOST", "").strip()
            and sender
            and 1 <= port <= 65535
            and bool(username) == bool(password)
        )
    return False


def _read_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError(f"{name} must be true or false.")
    return normalized in {"true", "1", "yes"}


def send_account_email(recipient: str, subject: str, body: str) -> None:
    mode = os.getenv("LIFELOG_EMAIL_BACKEND", "").strip().lower()
    if not mode:
        mode = "smtp" if os.getenv("LIFELOG_SMTP_HOST") else "console"

    if mode == "console":
        if os.getenv("APP_ENV", "development").lower() == "production":
            raise RuntimeError("Console email delivery is disabled in production.")
        LOGGER.warning(
            "Development-only account email for %s:\nSubject: %s\n%s",
            recipient,
            subject,
            body,
        )
        return
    if mode == "brevo":
        api_key = os.getenv("LIFELOG_BREVO_API_KEY", "").strip()
        sender = os.getenv("LIFELOG_SMTP_FROM_EMAIL", "").strip()
        if not api_key or not sender:
            raise ValueError(
                "Configure LIFELOG_BREVO_API_KEY and LIFELOG_SMTP_FROM_EMAIL "
                "for Brevo transactional email."
            )
        response = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            json={
                "sender": {
                    "name": os.getenv("LIFELOG_EMAIL_FROM_NAME", "LifeLog AI"),
                    "email": sender,
                },
                "to": [{"email": recipient}],
                "subject": subject,
                "textContent": body,
            },
            timeout=15,
        )
        if response.is_error:
            LOGGER.error(
                "Brevo rejected transactional email (HTTP %s).",
                response.status_code,
            )
            raise RuntimeError("Transactional email delivery failed.")
        return
    if mode != "smtp":
        raise ValueError(
            "LIFELOG_EMAIL_BACKEND must be 'smtp', 'brevo', or 'console'."
        )

    host = os.getenv("LIFELOG_SMTP_HOST", "").strip()
    sender = os.getenv("LIFELOG_SMTP_FROM_EMAIL", "").strip()
    try:
        port = int(os.getenv("LIFELOG_SMTP_PORT", "587"))
    except ValueError as error:
        raise ValueError("LIFELOG_SMTP_PORT must be a valid port.") from error
    if not host or not sender or not 1 <= port <= 65535:
        raise ValueError(
            "Configure LIFELOG_SMTP_HOST, LIFELOG_SMTP_FROM_EMAIL, and a valid "
            "LIFELOG_SMTP_PORT for account email."
        )

    use_ssl = _read_flag("LIFELOG_SMTP_USE_SSL", False)
    use_starttls = _read_flag("LIFELOG_SMTP_USE_STARTTLS", True)
    if use_ssl and use_starttls:
        raise ValueError("Configure SMTP SSL or STARTTLS, not both.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    context = ssl.create_default_context()
    with smtp_class(host, port, timeout=30, context=context) if use_ssl else smtp_class(
        host, port, timeout=30
    ) as server:
        if use_starttls:
            server.starttls(context=context)
        username = os.getenv("LIFELOG_SMTP_USERNAME", "").strip()
        password = os.getenv("LIFELOG_SMTP_PASSWORD", "")
        if bool(username) != bool(password):
            raise ValueError("Configure both SMTP username and password, or neither.")
        if username:
            server.login(username, password)
        refused = server.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
