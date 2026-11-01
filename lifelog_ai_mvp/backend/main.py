import io
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date
from typing import Callable

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy import delete, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, make_engine, session_factory
from .mail import email_delivery_configured, send_account_email
from .models import (
    AccountMemory,
    AccountMood,
    AccountProfile,
    AccountReminder,
    AccountSession,
    AccountTask,
    AccountToken,
    AccountUser,
)
from .schemas import (
    ForgotPasswordRequest,
    GenerationRequest,
    LoginRequest,
    MemoryCreate,
    MemoryResponse,
    MemoryUpdate,
    MessageResponse,
    MoodResponse,
    MoodUpdate,
    ProfileResponse,
    ProfileUpdate,
    RegisterRequest,
    ResetPasswordRequest,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    TokenRequest,
    UserResponse,
)
from .security import (
    CSRF_COOKIE,
    RESET_TOKEN_LIFETIME,
    SESSION_COOKIE,
    TOKEN_LIFETIME,
    clear_rate_limit,
    clear_user_sessions,
    consume_token,
    create_opaque_token,
    enforce_rate_limit,
    hash_password,
    hash_token,
    new_session,
    session_cookie_secure,
    utc_now,
    verify_password,
)


LOGGER = logging.getLogger(__name__)
PROFILE_IMAGE_MAX_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_MOODS = {"Sunny", "Soft", "Focused", "Cloudy", "Restless"}


def _user_payload(user: AccountUser) -> UserResponse:
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        email_verified=user.email_verified,
        created_at=user.created_at.isoformat(),
    )


def _profile_payload(user: AccountUser, profile: AccountProfile) -> ProfileResponse:
    return ProfileResponse(
        full_name=user.full_name,
        email=user.email,
        email_verified=user.email_verified,
        has_profile_image=profile.avatar_data is not None,
        preferred_language=profile.preferred_language,
        timezone=profile.timezone,
        writing_style=profile.writing_style,
        journal_tone=profile.journal_tone,
        interests=profile.interests,
        goals=profile.goals,
        reminder_time=profile.reminder_time,
        email_notifications=profile.email_notifications,
        in_app_notifications=profile.in_app_notifications,
    )


def _memory_payload(memory: AccountMemory) -> MemoryResponse:
    return MemoryResponse(
        id=memory.id,
        title=memory.title,
        source_text=memory.source_text,
        mode=memory.mode,
        tags=memory.tags,
        mood=memory.mood,
        memory_date=memory.memory_date,
        result=json.loads(memory.result_json),
        created_at=memory.created_at.isoformat(),
    )


def _task_payload(task: AccountTask) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        memory_id=task.memory_id,
        title=task.title,
        description=task.description,
        due_date=task.due_date,
        due_time=task.due_time,
        priority=task.priority,
        completed=task.completed,
        reminder_enabled=task.reminder_enabled,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
    )


def _mood_payload(mood: AccountMood) -> MoodResponse:
    return MoodResponse(
        id=mood.id,
        mood=mood.mood,
        checkin_date=mood.checkin_date,
        created_at=mood.created_at.isoformat(),
    )


def _send_token_email(
    user: AccountUser, token: str, purpose: str, email_sender: Callable
) -> None:
    frontend = os.getenv("LIFELOG_FRONTEND_URL", "http://localhost:5173").rstrip("/")
    if purpose == "verify_email":
        link = f"{frontend}/?verify={token}"
        subject = "Verify your LifeLog AI email"
        instruction = "Use this link to verify your email address."
    else:
        link = f"{frontend}/?reset={token}"
        subject = "Reset your LifeLog AI password"
        instruction = "Use this link to choose a new password."
    email_sender(
        user.email,
        subject,
        f"Hello {user.full_name},\n\n{instruction}\n\n{link}\n\n"
        "If you did not request this, you can ignore this message.",
    )


def create_app(
    database_url: str | None = None,
    email_sender: Callable | None = None,
    engine: Engine | None = None,
    create_schema: bool | None = None,
    secure_cookies: bool | None = None,
) -> FastAPI:
    app_engine = engine or make_engine(database_url)
    session_maker = session_factory(app_engine)
    deliver_email = email_sender or send_account_email
    initialize_schema = (
        os.getenv("LIFELOG_AUTO_CREATE_SCHEMA", "true").lower() == "true"
        if create_schema is None else create_schema
    )
    cookie_secure = (
        session_cookie_secure() if secure_cookies is None else secure_cookies
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if initialize_schema:
            Base.metadata.create_all(app_engine)
        yield
        if engine is None:
            app_engine.dispose()

    app = FastAPI(title="LifeLog AI API", version="0.1.0", lifespan=lifespan)
    app.state.session_maker = session_maker
    app.state.engine = app_engine
    app.state.email_sender = deliver_email
    app.state.cookie_secure = cookie_secure

    allowed_origin = os.getenv("LIFELOG_FRONTEND_ORIGIN", "http://localhost:5173")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[allowed_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    def db_dependency():
        db = session_maker()
        try:
            yield db
        finally:
            db.close()

    def require_csrf(request: Request) -> None:
        cookie_token = request.cookies.get(CSRF_COOKIE, "")
        header_token = request.headers.get("X-CSRF-Token", "")
        if (
            not cookie_token
            or not header_token
            or not hmac.compare_digest(cookie_token, header_token)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed. Refresh and try again.",
            )

    def current_user(
        request: Request,
        db: Session = Depends(db_dependency),
    ) -> AccountUser:
        raw_token = request.cookies.get(SESSION_COOKIE)
        if not raw_token:
            raise HTTPException(status_code=401, detail="Sign in to continue.")
        session_record = db.get(AccountSession, hash_token(raw_token))
        now = utc_now()
        if session_record is None or session_record.expires_at <= now:
            if session_record is not None:
                db.delete(session_record)
                db.commit()
            raise HTTPException(status_code=401, detail="Your session has expired.")
        user = db.get(AccountUser, session_record.user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Sign in to continue.")
        return user

    CSRF = Depends(require_csrf)
    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/auth/csrf", response_model=MessageResponse)
    def get_csrf(response: Response):
        token = create_opaque_token()
        response.set_cookie(
            CSRF_COOKIE,
            token,
            httponly=False,
            secure=app.state.cookie_secure,
            samesite="lax",
            path="/",
        )
        return {"message": "CSRF token issued."}

    @app.post(
        "/api/auth/register",
        response_model=MessageResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[CSRF],
    )
    def register(
        payload: RegisterRequest,
        request: Request,
        db: Session = Depends(db_dependency),
    ):
        if not enforce_rate_limit(
            db, "register", request.client.host if request.client else "unknown"
        ):
            db.commit()
            raise HTTPException(status_code=429, detail="Too many registration attempts.")
        email = str(payload.email).strip().lower()
        if db.scalar(select(AccountUser.id).where(AccountUser.email == email)):
            db.commit()
            raise HTTPException(status_code=409, detail="An account already uses this email.")

        user = AccountUser(
            full_name=payload.full_name,
            email=email,
            password_hash=hash_password(payload.password),
            email_verified=False,
            created_at=utc_now(),
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="An account already uses this email.",
            ) from error
        db.add(AccountProfile(user_id=user.id))
        token = create_opaque_token()
        db.add(
            AccountToken(
                token_hash=hash_token(token),
                user_id=user.id,
                purpose="verify_email",
                expires_at=utc_now() + TOKEN_LIFETIME,
                created_at=utc_now(),
            )
        )
        try:
            _send_token_email(user, token, "verify_email", app.state.email_sender)
            db.commit()
        except Exception as error:
            db.rollback()
            LOGGER.exception("Could not deliver account verification email.")
            raise HTTPException(
                status_code=503,
                detail="Account email delivery is unavailable. Try again later.",
            ) from error
        return {"message": "Account created. Check your email to verify it before signing in."}

    @app.post(
        "/api/auth/verify-email",
        response_model=MessageResponse,
        dependencies=[CSRF],
    )
    def verify_email(payload: TokenRequest, db: Session = Depends(db_dependency)):
        token_record = consume_token(db, payload.token, "verify_email")
        if token_record is None:
            db.commit()
            raise HTTPException(status_code=400, detail="Verification link is invalid or expired.")
        user = db.get(AccountUser, token_record.user_id)
        if user is None:
            db.commit()
            raise HTTPException(status_code=400, detail="Verification link is invalid or expired.")
        user.email_verified = True
        db.commit()
        return {"message": "Email verified. You can now sign in."}

    @app.post(
        "/api/auth/resend-verification",
        response_model=MessageResponse,
        dependencies=[CSRF],
    )
    def resend_verification(
        payload: ForgotPasswordRequest,
        request: Request,
        db: Session = Depends(db_dependency),
    ):
        if not enforce_rate_limit(
            db,
            "verify",
            request.client.host if request.client else "unknown",
            str(payload.email),
        ):
            db.commit()
            raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
        email = str(payload.email).strip().lower()
        user = db.scalar(select(AccountUser).where(AccountUser.email == email))
        if user is not None and not user.email_verified:
            db.execute(
                update(AccountToken)
                .where(
                    AccountToken.user_id == user.id,
                    AccountToken.purpose == "verify_email",
                    AccountToken.consumed_at.is_(None),
                )
                .values(consumed_at=utc_now())
            )
            token = create_opaque_token()
            db.add(
                AccountToken(
                    token_hash=hash_token(token),
                    user_id=user.id,
                    purpose="verify_email",
                    expires_at=utc_now() + TOKEN_LIFETIME,
                    created_at=utc_now(),
                )
            )
            try:
                _send_token_email(user, token, "verify_email", app.state.email_sender)
            except Exception as error:
                db.rollback()
                LOGGER.exception("Could not resend account verification email.")
                raise HTTPException(status_code=503, detail="Email delivery is unavailable.") from error
        db.commit()
        return {"message": "If the account needs verification, a link has been sent."}

    @app.post(
        "/api/auth/login",
        response_model=UserResponse,
        dependencies=[CSRF],
    )
    def login(
        payload: LoginRequest,
        request: Request,
        response: Response,
        db: Session = Depends(db_dependency),
    ):
        email = str(payload.email).strip().lower()
        if not enforce_rate_limit(
            db,
            "login",
            request.client.host if request.client else "unknown",
            email,
        ):
            db.commit()
            raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try later.")
        user = db.scalar(select(AccountUser).where(AccountUser.email == email))
        if user is None or not verify_password(payload.password, user.password_hash):
            db.commit()
            raise HTTPException(status_code=401, detail="Email or password is incorrect.")
        if not user.email_verified:
            db.commit()
            raise HTTPException(
                status_code=403,
                detail="Verify your email before signing in.",
                headers={"X-Account-Verification": "required"},
            )
        clear_rate_limit(
            db,
            "login",
            request.client.host if request.client else "unknown",
            email,
        )
        raw_token, expires_at = new_session(db, user.id, payload.remember_me)
        db.commit()
        cookie_options = {
            "httponly": True,
            "secure": app.state.cookie_secure,
            "samesite": "lax",
            "path": "/",
        }
        if payload.remember_me:
            cookie_options["max_age"] = max(
                0, int((expires_at - utc_now()).total_seconds())
            )
        response.set_cookie(SESSION_COOKIE, raw_token, **cookie_options)
        return _user_payload(user)

    @app.post(
        "/api/auth/logout",
        response_model=MessageResponse,
        dependencies=[CSRF],
    )
    def logout(
        request: Request,
        response: Response,
        db: Session = Depends(db_dependency),
    ):
        raw_token = request.cookies.get(SESSION_COOKIE)
        if raw_token:
            db.execute(
                delete(AccountSession).where(
                    AccountSession.token_hash == hash_token(raw_token)
                )
            )
            db.commit()
        response.delete_cookie(
            SESSION_COOKIE,
            path="/",
            secure=app.state.cookie_secure,
            httponly=True,
            samesite="lax",
        )
        return {"message": "Signed out."}

    @app.get("/api/auth/me", response_model=UserResponse)
    def me(user: AccountUser = Depends(current_user)):
        return _user_payload(user)

    @app.post(
        "/api/auth/forgot-password",
        response_model=MessageResponse,
        dependencies=[CSRF],
    )
    def forgot_password(
        payload: ForgotPasswordRequest,
        request: Request,
        db: Session = Depends(db_dependency),
    ):
        email = str(payload.email).strip().lower()
        if not enforce_rate_limit(
            db,
            "reset",
            request.client.host if request.client else "unknown",
            email,
        ):
            db.commit()
            raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
        user = db.scalar(select(AccountUser).where(AccountUser.email == email))
        if user is not None and user.email_verified:
            db.execute(
                update(AccountToken)
                .where(
                    AccountToken.user_id == user.id,
                    AccountToken.purpose == "reset_password",
                    AccountToken.consumed_at.is_(None),
                )
                .values(consumed_at=utc_now())
            )
            token = create_opaque_token()
            db.add(
                AccountToken(
                    token_hash=hash_token(token),
                    user_id=user.id,
                    purpose="reset_password",
                    expires_at=utc_now() + RESET_TOKEN_LIFETIME,
                    created_at=utc_now(),
                )
            )
            try:
                _send_token_email(user, token, "reset_password", app.state.email_sender)
            except Exception:
                db.rollback()
                LOGGER.exception("Could not deliver password reset email.")
                return {
                    "message": "If a verified account exists for that email, reset instructions will be sent."
                }
        db.commit()
        return {
            "message": "If a verified account exists for that email, reset instructions will be sent."
        }

    @app.post(
        "/api/auth/reset-password",
        response_model=MessageResponse,
        dependencies=[CSRF],
    )
    def reset_password(
        payload: ResetPasswordRequest,
        db: Session = Depends(db_dependency),
    ):
        token_record = consume_token(db, payload.token, "reset_password")
        if token_record is None:
            db.commit()
            raise HTTPException(status_code=400, detail="Reset link is invalid or expired.")
        user = db.get(AccountUser, token_record.user_id)
        if user is None or not user.email_verified:
            db.commit()
            raise HTTPException(status_code=400, detail="Reset link is invalid or expired.")
        user.password_hash = hash_password(payload.password)
        clear_user_sessions(db, user.id)
        db.execute(
            update(AccountToken)
            .where(
                AccountToken.user_id == user.id,
                AccountToken.purpose == "reset_password",
                AccountToken.consumed_at.is_(None),
            )
            .values(consumed_at=utc_now())
        )
        db.commit()
        return {"message": "Password changed. Sign in with your new password."}

    @app.get("/api/profile", response_model=ProfileResponse)
    def get_profile(
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        profile = db.get(AccountProfile, user.id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found.")
        return _profile_payload(user, profile)

    @app.patch(
        "/api/profile",
        response_model=ProfileResponse,
        dependencies=[CSRF],
    )
    def update_profile(
        payload: ProfileUpdate,
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        profile = db.get(AccountProfile, user.id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found.")
        user.full_name = payload.full_name
        for field in (
            "preferred_language",
            "timezone",
            "writing_style",
            "journal_tone",
            "interests",
            "goals",
            "reminder_time",
            "email_notifications",
            "in_app_notifications",
        ):
            setattr(profile, field, getattr(payload, field))
        db.execute(
            delete(AccountReminder).where(
                AccountReminder.task_id.in_(
                    select(AccountTask.id).where(AccountTask.user_id == user.id)
                ),
                AccountReminder.status == "pending",
            )
        )
        db.commit()
        return _profile_payload(user, profile)

    @app.put(
        "/api/profile/avatar",
        response_model=ProfileResponse,
        dependencies=[CSRF],
    )
    async def update_avatar(
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
        file: UploadFile = File(...),
    ):
        contents = await file.read(PROFILE_IMAGE_MAX_BYTES + 1)
        if len(contents) > PROFILE_IMAGE_MAX_BYTES:
            raise HTTPException(status_code=413, detail="Image must be no larger than 5 MB.")
        try:
            image = Image.open(io.BytesIO(contents))
            if image.format not in ALLOWED_IMAGE_FORMATS:
                raise HTTPException(status_code=415, detail="Use a JPEG, PNG, or WebP image.")
            if image.width * image.height > 25_000_000:
                raise HTTPException(
                    status_code=413,
                    detail="Image dimensions are too large. Use an image under 25 megapixels.",
                )
            image.verify()
            image = Image.open(io.BytesIO(contents))
            image.thumbnail((512, 512))
            output = io.BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=88, optimize=True)
        except UnidentifiedImageError as error:
            raise HTTPException(status_code=415, detail="Upload a valid image file.") from error
        except Image.DecompressionBombError as error:
            raise HTTPException(status_code=413, detail="Image dimensions are too large.") from error
        except OSError as error:
            raise HTTPException(status_code=415, detail="Upload a valid image file.") from error
        profile = db.get(AccountProfile, user.id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found.")
        profile.avatar_data = output.getvalue()
        db.commit()
        return _profile_payload(user, profile)

    @app.delete(
        "/api/profile/avatar",
        response_model=ProfileResponse,
        dependencies=[CSRF],
    )
    def delete_avatar(
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        profile = db.get(AccountProfile, user.id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found.")
        profile.avatar_data = None
        db.commit()
        return _profile_payload(user, profile)

    @app.get("/api/profile/avatar")
    def get_avatar(
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        profile = db.get(AccountProfile, user.id)
        if profile is None or profile.avatar_data is None:
            raise HTTPException(status_code=404, detail="Profile image not found.")
        return StreamingResponse(
            io.BytesIO(profile.avatar_data),
            media_type="image/jpeg",
            headers={"Cache-Control": "private, no-store"},
        )

    @app.get("/api/memories", response_model=list[MemoryResponse])
    def list_memories(
        search: str = "",
        tag: str = "",
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        query = select(AccountMemory).where(AccountMemory.user_id == user.id)
        if search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(
                AccountMemory.title.ilike(pattern)
                | AccountMemory.source_text.ilike(pattern)
                | AccountMemory.result_json.ilike(pattern)
                | AccountMemory.tags.ilike(pattern)
            )
        if tag.strip():
            query = query.where(AccountMemory.tags.ilike(f"%{tag.strip()}%"))
        memories = db.scalars(
            query.order_by(AccountMemory.memory_date.desc(), AccountMemory.id.desc())
        )
        return [_memory_payload(memory) for memory in memories]

    @app.post(
        "/api/memories",
        response_model=MemoryResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[CSRF],
    )
    def create_memory(
        payload: MemoryCreate,
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        memory = AccountMemory(
            user_id=user.id,
            title=payload.title,
            source_text=payload.source_text,
            mode=payload.mode,
            result_json=json.dumps(payload.result, ensure_ascii=False),
            tags=payload.tags,
            mood=payload.mood,
            memory_date=payload.memory_date,
            created_at=utc_now(),
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        return _memory_payload(memory)

    @app.patch(
        "/api/memories/{memory_id}",
        response_model=MemoryResponse,
        dependencies=[CSRF],
    )
    def update_memory(
        memory_id: int,
        payload: MemoryUpdate,
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        memory = db.scalar(
            select(AccountMemory).where(
                AccountMemory.id == memory_id,
                AccountMemory.user_id == user.id,
            )
        )
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found.")
        values = payload.model_dump(exclude_unset=True)
        for field in ("title", "source_text", "mode"):
            if field in values and not values[field]:
                raise HTTPException(status_code=422, detail=f"{field} cannot be empty.")
        for field, value in values.items():
            if value is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"{field} cannot be cleared.",
                )
            setattr(
                memory,
                "result_json" if field == "result" else field,
                json.dumps(value, ensure_ascii=False) if field == "result" else value,
            )
        db.commit()
        db.refresh(memory)
        return _memory_payload(memory)

    @app.delete(
        "/api/memories/{memory_id}",
        response_model=MessageResponse,
        dependencies=[CSRF],
    )
    def delete_memory(
        memory_id: int,
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        memory = db.scalar(
            select(AccountMemory).where(
                AccountMemory.id == memory_id,
                AccountMemory.user_id == user.id,
            )
        )
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found.")
        db.delete(memory)
        db.commit()
        return {"message": "Memory deleted."}

    @app.get("/api/tasks", response_model=list[TaskResponse])
    def list_tasks(
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        tasks = db.scalars(
            select(AccountTask)
            .where(AccountTask.user_id == user.id)
            .order_by(AccountTask.completed, AccountTask.due_date, AccountTask.id.desc())
        )
        return [_task_payload(task) for task in tasks]

    @app.post(
        "/api/tasks",
        response_model=TaskResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[CSRF],
    )
    def create_task(
        payload: TaskCreate,
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        if payload.reminder_enabled and payload.due_date is None:
            raise HTTPException(
                status_code=422,
                detail="A due date is required to enable email reminders.",
            )
        if payload.reminder_enabled:
            profile = db.get(AccountProfile, user.id)
            if profile is not None and not profile.email_notifications:
                raise HTTPException(
                    status_code=422,
                    detail="Enable email notifications in your profile first.",
                )
            if not email_delivery_configured():
                raise HTTPException(
                    status_code=503,
                    detail="Configure a real email provider in .env before enabling reminders.",
                )
        if payload.memory_id is not None:
            memory_exists = db.scalar(
                select(AccountMemory.id).where(
                    AccountMemory.id == payload.memory_id,
                    AccountMemory.user_id == user.id,
                )
            )
            if memory_exists is None:
                raise HTTPException(status_code=404, detail="Source memory not found.")
        now = utc_now()
        task = AccountTask(
            user_id=user.id,
            memory_id=payload.memory_id,
            title=payload.title,
            description=payload.description,
            due_date=payload.due_date,
            due_time=payload.due_time,
            priority=payload.priority,
            completed=False,
            reminder_enabled=payload.reminder_enabled,
            created_at=now,
            updated_at=now,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return _task_payload(task)

    @app.patch(
        "/api/tasks/{task_id}",
        response_model=TaskResponse,
        dependencies=[CSRF],
    )
    def update_task(
        task_id: int,
        payload: TaskUpdate,
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        task = db.scalar(
            select(AccountTask).where(
                AccountTask.id == task_id,
                AccountTask.user_id == user.id,
            )
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        values = payload.model_dump(exclude_unset=True)
        if "title" in values and not values["title"]:
            raise HTTPException(status_code=422, detail="Task title cannot be empty.")
        if any(
            value is None and field not in {"memory_id", "due_date", "due_time"}
            for field, value in values.items()
        ):
            raise HTTPException(
                status_code=422,
                detail="Required task fields cannot be cleared.",
            )
        if values.get("memory_id") is not None:
            memory_exists = db.scalar(
                select(AccountMemory.id).where(
                    AccountMemory.id == values["memory_id"],
                    AccountMemory.user_id == user.id,
                )
            )
            if memory_exists is None:
                raise HTTPException(status_code=404, detail="Source memory not found.")
        for field, value in values.items():
            setattr(task, field, value)
        if task.reminder_enabled and task.due_date is None:
            raise HTTPException(
                status_code=422,
                detail="A due date is required to enable email reminders.",
            )
        if task.reminder_enabled and (
            "reminder_enabled" in values or "due_date" in values
        ):
            profile = db.get(AccountProfile, user.id)
            if profile is not None and not profile.email_notifications:
                raise HTTPException(
                    status_code=422,
                    detail="Enable email notifications in your profile first.",
                )
            if not email_delivery_configured():
                raise HTTPException(
                    status_code=503,
                    detail="Configure a real email provider in .env before enabling reminders.",
                )
        task.updated_at = utc_now()
        db.execute(
            delete(AccountReminder).where(
                AccountReminder.task_id == task.id,
                AccountReminder.status == "pending",
            )
        )
        db.commit()
        db.refresh(task)
        return _task_payload(task)

    @app.delete(
        "/api/tasks/{task_id}",
        response_model=MessageResponse,
        dependencies=[CSRF],
    )
    def delete_task(
        task_id: int,
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        task = db.scalar(
            select(AccountTask).where(
                AccountTask.id == task_id,
                AccountTask.user_id == user.id,
            )
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        db.delete(task)
        db.commit()
        return {"message": "Task deleted."}

    @app.get("/api/moods", response_model=list[MoodResponse])
    def list_moods(
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        moods = db.scalars(
            select(AccountMood)
            .where(AccountMood.user_id == user.id)
            .order_by(AccountMood.checkin_date.desc())
            .limit(365)
        )
        return [_mood_payload(mood) for mood in moods]

    @app.put(
        "/api/moods",
        response_model=MoodResponse,
        dependencies=[CSRF],
    )
    def save_mood(
        payload: MoodUpdate,
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        mood = db.scalar(
            select(AccountMood).where(
                AccountMood.user_id == user.id,
                AccountMood.checkin_date == payload.checkin_date,
            )
        )
        if mood is None:
            mood = AccountMood(
                user_id=user.id,
                mood=payload.mood,
                checkin_date=payload.checkin_date,
                created_at=utc_now(),
            )
            db.add(mood)
        else:
            mood.mood = payload.mood
        db.commit()
        db.refresh(mood)
        return _mood_payload(mood)

    @app.post(
        "/api/generation",
        dependencies=[CSRF],
    )
    def generate_content(
        payload: GenerationRequest,
        user: AccountUser = Depends(current_user),
        db: Session = Depends(db_dependency),
    ):
        from generation.client import api_key
        from generation.pipeline import generate_lifelog

        if not api_key():
            raise HTTPException(
                status_code=503,
                detail=(
                    "AI generation is not configured. Set LIFELOG_LLM_API_KEY "
                    "(or OPENAI_API_KEY) and the model settings in .env."
                ),
            )
        profile = db.get(AccountProfile, user.id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found.")
        try:
            result, provider_status = generate_lifelog(
                payload.source_text,
                payload.mode,
                profile={
                    "writing_style": profile.writing_style,
                    "journal_tone": profile.journal_tone,
                    "interests": profile.interests,
                },
                custom_prompt=payload.custom_prompt,
                output_length=payload.output_length,
            )
        except Exception as error:
            LOGGER.error("AI generation request failed (%s).", type(error).__name__)
            raise HTTPException(
                status_code=502,
                detail="The configured AI provider could not complete this request.",
            ) from error
        return {"result": result, "provider": provider_status}

    return app


app = create_app()
