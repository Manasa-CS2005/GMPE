import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from pwdlib import PasswordHash
from sqlalchemy import case, delete, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .models import AccountSession, AccountToken, AuthRateLimit


PASSWORD_HASHER = PasswordHash.recommended()
SESSION_COOKIE = "lifelog_session"
CSRF_COOKIE = "lifelog_csrf"
SESSION_LENGTH = timedelta(hours=24)
REMEMBERED_SESSION_LENGTH = timedelta(days=30)
TOKEN_LIFETIME = timedelta(hours=24)
RESET_TOKEN_LIFETIME = timedelta(hours=1)
RATE_WINDOW = timedelta(minutes=15)
RATE_LIMITS = {"login": 10, "register": 5, "verify": 5, "reset": 5}
IP_RATE_LIMITS = {"login": 30, "register": 10, "verify": 15, "reset": 15}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def validate_password_strength(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")
    categories = (
        any(character.islower() for character in password),
        any(character.isupper() for character in password),
        any(character.isdigit() for character in password),
        any(not character.isalnum() for character in password),
    )
    if sum(categories) < 3:
        raise ValueError(
            "Password must include at least three of: lowercase, uppercase, "
            "number, and symbol."
        )


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PASSWORD_HASHER.verify(password, password_hash)


def consume_token(db: Session, token: str, purpose: str) -> AccountToken | None:
    token_hash = hash_token(token)
    now = utc_now()
    result = db.execute(
        update(AccountToken)
        .where(
            AccountToken.token_hash == token_hash,
            AccountToken.purpose == purpose,
            AccountToken.consumed_at.is_(None),
            AccountToken.expires_at > now,
        )
        .values(consumed_at=now)
    )
    if result.rowcount != 1:
        return None
    return db.get(AccountToken, token_hash)


def enforce_rate_limit(
    db: Session, action: str, remote_address: str, identifier: str = ""
) -> bool:
    limit = RATE_LIMITS[action]
    identities = {remote_address.strip()}
    if identifier.strip():
        identities.add(f"{remote_address.strip()}:{identifier.strip().lower()}")
    now = utc_now()
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        insert_statement = sqlite_insert
    elif dialect == "postgresql":
        insert_statement = postgresql_insert
    else:
        raise RuntimeError(f"Unsupported database dialect for rate limits: {dialect}.")

    expired = AuthRateLimit.window_started_at <= now - RATE_WINDOW
    allowed = True
    for identity in identities:
        statement = insert_statement(AuthRateLimit).values(
            action=action,
            bucket_hash=hash_token(identity),
            window_started_at=now,
            attempts=1,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[AuthRateLimit.action, AuthRateLimit.bucket_hash],
            set_={
                "window_started_at": case(
                    (expired, now),
                    else_=AuthRateLimit.window_started_at,
                ),
                "attempts": case((expired, 1), else_=AuthRateLimit.attempts + 1),
            },
        ).returning(AuthRateLimit.attempts)
        attempts = db.scalar(statement)
        bucket_limit = IP_RATE_LIMITS[action] if identity == remote_address.strip() else limit
        allowed = allowed and attempts is not None and attempts <= bucket_limit
    return allowed


def clear_rate_limit(
    db: Session, action: str, remote_address: str, identifier: str = ""
) -> None:
    identities = {remote_address.strip()}
    if identifier.strip():
        identities.add(f"{remote_address.strip()}:{identifier.strip().lower()}")
    db.execute(
        delete(AuthRateLimit).where(
            AuthRateLimit.action == action,
            AuthRateLimit.bucket_hash.in_(
                [hash_token(identity) for identity in identities]
            ),
        )
    )


def new_session(db: Session, user_id: int, remember_me: bool) -> tuple[str, datetime]:
    token = create_opaque_token()
    expires_at = utc_now() + (
        REMEMBERED_SESSION_LENGTH if remember_me else SESSION_LENGTH
    )
    db.add(
        AccountSession(
            token_hash=hash_token(token),
            user_id=user_id,
            expires_at=expires_at,
            created_at=utc_now(),
        )
    )
    return token, expires_at


def clear_user_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(AccountSession).where(AccountSession.user_id == user_id))


def session_cookie_secure() -> bool:
    return os.getenv("APP_ENV", "development").lower() == "production"
