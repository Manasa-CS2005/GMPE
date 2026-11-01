import json

from .client import complete_json
from .demo import demo_result
from .prompts import GENERATION_SYSTEM, length_instruction, mode_instruction
from .schemas import StructuredDay


def generate_mode_outputs(note, mode, structured_day, profile=None, custom_prompt="", output_length="Medium"):
    profile = profile or {}
    structured_payload = (
        structured_day.model_dump()
        if isinstance(structured_day, StructuredDay)
        else structured_day
    )
    user_prompt = f"""
Selected generation mode: {mode}
Mode instruction: {mode_instruction(mode)}
Output length: {output_length}. {length_instruction(output_length)}
Writing style preference: {profile.get("writing_style") or "Reflective"}
Journal tone preference: {profile.get("journal_tone") or "Warm"}
User interests (do not invent related events): {profile.get("interests") or "none provided"}
Custom instructions: {custom_prompt.strip() or "none"}

Validated structured day (use this as the factual spine):
{json.dumps(structured_payload, ensure_ascii=False, indent=2)}

Original source:
{note}

Generate the LifeLog outputs. Match the selected mode in tone.
"""
    data = complete_json(GENERATION_SYSTEM, user_prompt, temperature=0.7)
    defaults = demo_result(note, mode, custom_prompt)
    for key, value in defaults.items():
        if key not in data or data[key] is None:
            data[key] = value
    data["structured_day"] = structured_payload
    data["tasks"] = structured_payload.get("pending_tasks", data.get("tasks", []))
    return data
