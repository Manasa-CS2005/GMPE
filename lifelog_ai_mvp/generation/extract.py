from datetime import date

from pydantic import ValidationError

from .client import complete_json
from .heuristics import extract_completed_actions, extract_pending_tasks
from .prompts import EXTRACTION_SYSTEM
from .schemas import StructuredDay


def fallback_structured_day(note):
    clean_note = " ".join(note.split())
    return StructuredDay(
        date=date.today().isoformat(),
        summary=clean_note[:240],
        completed_tasks=extract_completed_actions(note),
        pending_tasks=extract_pending_tasks(note),
        source_references=["daily note"],
    )


def extract_structured_day(note):
    """Stage 1: convert source text into a validated StructuredDay."""
    try:
        data = complete_json(
            EXTRACTION_SYSTEM,
            f"Today's date: {date.today().isoformat()}\n\nSource material:\n{note}",
            temperature=0.2,
        )
        if not data.get("date"):
            data["date"] = date.today().isoformat()
        return StructuredDay.model_validate(data)
    except (ValidationError, ValueError, RuntimeError, OSError):
        return fallback_structured_day(note)
