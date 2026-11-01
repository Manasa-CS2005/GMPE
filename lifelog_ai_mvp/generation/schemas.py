from datetime import date

from pydantic import BaseModel, Field


class StructuredDay(BaseModel):
    date: str = Field(default_factory=lambda: date.today().isoformat())
    summary: str = ""
    events: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)
    mood: str = ""
    completed_tasks: list[str] = Field(default_factory=list)
    pending_tasks: list[str] = Field(default_factory=list)
    future_plans: list[str] = Field(default_factory=list)
    important_moments: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)


class StructuredJournal(BaseModel):
    date: str = Field(default_factory=lambda: date.today().isoformat())
    title: str = "Daily journal"
    opening: str = ""
    events: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)
    feelings: list[str] = Field(default_factory=list)
    reflection: str = ""
    gratitude: list[str] = Field(default_factory=list)
    closing: str = ""


class StructuredVlog(BaseModel):
    title: str = "A day in my life"
    hook: str = ""
    scenes: list[str] = Field(default_factory=list)
    voiceover: list[str] = Field(default_factory=list)
    b_roll: list[str] = Field(default_factory=list)
    closing: str = ""


class StructuredSocial(BaseModel):
    caption: str = ""
    alternatives: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    story_text: str = ""


class StructuredAnalogy(BaseModel):
    analogy: str = ""
    mapping: list[str] = Field(default_factory=list)
    simpler_version: str = ""
    detailed_version: str = ""
