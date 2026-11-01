from datetime import date

from pydantic import ValidationError

from .heuristics import extract_completed_actions, extract_pending_tasks
from .schemas import StructuredAnalogy, StructuredDay, StructuredJournal, StructuredSocial, StructuredVlog


def validate_day_result(result, note):
    """Validate and normalize structured generation output."""
    structured = result.get("structured_day", {})
    if not isinstance(structured, dict):
        structured = {}
    structured.setdefault("date", date.today().isoformat())
    structured.setdefault("summary", result.get("journal", "")[:240])
    structured.setdefault("pending_tasks", result.get("tasks", []))
    try:
        validated = StructuredDay.model_validate(structured)
    except ValidationError:
        validated = StructuredDay(
            date=date.today().isoformat(),
            summary=" ".join(note.split())[:240],
            pending_tasks=[str(task) for task in result.get("tasks", []) if str(task).strip()],
        )
    normalized = validated.model_dump()
    result["structured_day"] = normalized
    result["tasks"] = normalized["pending_tasks"]
    return normalize_structured_outputs(result, note)


def normalize_structured_outputs(result, note):
    fallback_tasks = extract_pending_tasks(note)
    result.setdefault("structured_journal", {})
    result.setdefault("structured_vlog", {})
    result.setdefault("structured_social", {})
    result.setdefault("structured_analogy", {})
    try:
        journal = StructuredJournal.model_validate(result["structured_journal"])
    except ValidationError:
        journal = StructuredJournal(
            opening=result.get("journal", ""),
            reflection=result.get("reflection", ""),
            closing="End of today's record.",
        )
    try:
        vlog = StructuredVlog.model_validate(result["structured_vlog"])
    except ValidationError:
        vlog = StructuredVlog(
            hook="A short look at today's memory.",
            scenes=["Opening shot of the day", "Main moment from the note", "Closing reflection"],
            voiceover=[result.get("vlog_script", "")],
            closing="That is one moment I want to remember.",
        )
    try:
        social = StructuredSocial.model_validate(result["structured_social"])
    except ValidationError:
        social = StructuredSocial(caption=result.get("social_caption", ""))
    try:
        analogy = StructuredAnalogy.model_validate(result["structured_analogy"])
    except ValidationError:
        analogy = StructuredAnalogy(simpler_version=result.get("journal", ""))
    result["structured_journal"] = journal.model_dump()
    result["structured_vlog"] = vlog.model_dump()
    result["structured_social"] = social.model_dump()
    result["structured_analogy"] = analogy.model_dump()
    if not result.get("social_caption"):
        result["social_caption"] = social.caption
    structured = result.get("structured_day", {})
    if not isinstance(structured, dict):
        structured = {}
    llm_pending = structured.get("pending_tasks", result.get("tasks", []))
    pending_tasks = [str(task).strip() for task in llm_pending if str(task).strip()]
    if not pending_tasks and fallback_tasks:
        pending_tasks = fallback_tasks
    structured["pending_tasks"] = pending_tasks
    if not structured.get("completed_tasks"):
        structured["completed_tasks"] = extract_completed_actions(note)
    result["structured_day"] = structured
    result["tasks"] = pending_tasks
    return result
