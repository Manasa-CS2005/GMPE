from .client import api_key
from .demo import demo_result
from .extract import extract_structured_day, fallback_structured_day
from .generate import generate_mode_outputs
from .transcribe import transcribe_audio
from .validate import validate_day_result
from .visual import generate_visual_image, generate_visual_prompt


def combine_source(note, extra_context=""):
    extra = (extra_context or "").strip()
    if extra:
        return f"{note.strip()}\n\nAttached document text:\n{extra}"
    return note.strip()


def generate_lifelog(note, mode, profile=None, extra_context="", custom_prompt="", output_length="Medium"):
    """
    Two-stage LifeLog pipeline from the blueprint:
    1. Day-understanding engine (validated StructuredDay)
    2. Mode-specific generation grounded in that structure
    """
    combined = combine_source(note, extra_context)
    if not api_key():
        structured = fallback_structured_day(combined)
        result = demo_result(combined, mode, custom_prompt)
        result["structured_day"] = structured.model_dump()
        result["tasks"] = structured.pending_tasks
        return validate_day_result(result, combined), "demo"

    structured = extract_structured_day(combined)
    generated = generate_mode_outputs(
        combined, mode, structured, profile, custom_prompt, output_length
    )
    return validate_day_result(generated, combined), "ai"


__all__ = [
    "generate_lifelog",
    "generate_visual_prompt",
    "generate_visual_image",
    "transcribe_audio",
]
