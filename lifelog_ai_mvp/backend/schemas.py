import re
from datetime import date, time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from .security import validate_password_strength


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    confirm_password: str = Field(min_length=12, max_length=256)

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Full name is required.")
        return normalized

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        validate_password_strength(self.password)
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    remember_me: bool = False


class TokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    password: str = Field(min_length=12, max_length=256)
    confirm_password: str = Field(min_length=12, max_length=256)

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        validate_password_strength(self.password)
        return self


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    email_verified: bool
    created_at: str


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    preferred_language: str = Field(default="en", min_length=2, max_length=16)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    writing_style: str = Field(default="Reflective", min_length=1, max_length=32)
    journal_tone: str = Field(default="Warm", min_length=1, max_length=32)
    interests: str = Field(default="", max_length=2000)
    goals: str = Field(default="", max_length=2000)
    reminder_time: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")
    email_notifications: bool = True
    in_app_notifications: bool = True

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Full name is required.")
        return normalized

    @field_validator("preferred_language")
    @classmethod
    def validate_language_code(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", value):
            raise ValueError("Use a valid language code, such as en or en-US.")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("Use a valid IANA time zone, such as Europe/London.") from error
        return value

    @field_validator("reminder_time")
    @classmethod
    def validate_reminder_time(cls, value: str) -> str:
        try:
            time.fromisoformat(value)
        except ValueError as error:
            raise ValueError("Reminder time must use HH:MM.") from error
        return value


class ProfileResponse(ProfileUpdate):
    model_config = ConfigDict(from_attributes=True)
    email: EmailStr
    email_verified: bool
    has_profile_image: bool


class MessageResponse(BaseModel):
    message: str


class MemoryCreate(BaseModel):
    title: str = Field(default="Untitled memory", min_length=1, max_length=120)
    source_text: str = Field(min_length=1, max_length=10000)
    mode: str = Field(default="Simple Journal", min_length=1, max_length=40)
    tags: str = Field(default="", max_length=500)
    mood: str = Field(default="", max_length=24)
    memory_date: date = Field(default_factory=date.today)
    result: dict = Field(default_factory=dict)

    @field_validator("title", "source_text", "mode", "tags", "mood")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not value:
            raise ValueError("A memory title is required.")
        return value

    @field_validator("source_text")
    @classmethod
    def validate_source_text(cls, value: str) -> str:
        if not value:
            raise ValueError("Memory text is required.")
        return value


class MemoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    source_text: str | None = Field(default=None, min_length=1, max_length=10000)
    mode: str | None = Field(default=None, min_length=1, max_length=40)
    tags: str | None = Field(default=None, max_length=500)
    mood: str | None = Field(default=None, max_length=24)
    memory_date: date | None = None
    result: dict | None = None

    @field_validator("title", "source_text", "mode", "tags", "mood")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class MemoryResponse(BaseModel):
    id: int
    title: str
    source_text: str
    mode: str
    tags: str
    mood: str
    memory_date: date
    result: dict
    created_at: str


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=2000)
    memory_id: int | None = None
    due_date: date | None = None
    due_time: time | None = None
    priority: Literal["low", "normal", "high"] = "normal"
    reminder_enabled: bool = False

    @field_validator("title", "description")
    @classmethod
    def trim_task_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("title")
    @classmethod
    def validate_task_title(cls, value: str) -> str:
        if not value:
            raise ValueError("A task title is required.")
        return value


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=2000)
    memory_id: int | None = None
    due_date: date | None = None
    due_time: time | None = None
    priority: Literal["low", "normal", "high"] | None = None
    reminder_enabled: bool | None = None
    completed: bool | None = None

    @field_validator("title", "description")
    @classmethod
    def trim_optional_task_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class TaskResponse(BaseModel):
    id: int
    memory_id: int | None
    title: str
    description: str
    due_date: date | None
    due_time: time | None
    priority: str
    completed: bool
    reminder_enabled: bool
    created_at: str
    updated_at: str


class MoodUpdate(BaseModel):
    mood: Literal["Sunny", "Soft", "Focused", "Cloudy", "Restless"]
    checkin_date: date = Field(default_factory=date.today)


class MoodResponse(BaseModel):
    id: int
    mood: str
    checkin_date: date
    created_at: str


class GenerationRequest(BaseModel):
    source_text: str = Field(min_length=1, max_length=10000)
    mode: Literal[
        "Simple Journal",
        "Personal Persona",
        "Structured Day",
        "Reflection",
        "Explain Through an Analogy",
        "Vlog Creator",
        "Social Media",
        "Custom Prompt",
    ] = "Simple Journal"
    output_length: Literal["Short", "Medium", "Detailed"] = "Medium"
    custom_prompt: str = Field(default="", max_length=2000)

    @field_validator("source_text", "custom_prompt")
    @classmethod
    def trim_generation_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("source_text")
    @classmethod
    def validate_generation_source(cls, value: str) -> str:
        if not value:
            raise ValueError("Add a note before generating.")
        return value
