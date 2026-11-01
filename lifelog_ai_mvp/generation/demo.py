from datetime import date

from .heuristics import extract_completed_actions, extract_pending_tasks


def demo_result(note, mode, custom_prompt=""):
    """Fallback so the interface can be explored without an API key."""
    clean_note = " ".join(note.split())
    pending_tasks = extract_pending_tasks(note)
    completed_actions = extract_completed_actions(note)
    analogy = (
        "This day is like a notebook page: the facts you wrote down are the ink, "
        "and anything not written is left blank on purpose."
    )
    if mode == "Explain Through an Analogy":
        journal = f"If I explain today through an analogy: {analogy} The note itself said: {clean_note}"
    elif mode == "Custom Prompt" and custom_prompt.strip():
        journal = f"Custom instructions (demo): {custom_prompt.strip()}\n\nBased only on your note: {clean_note}"
    else:
        journal = f"Today, I wanted to remember this: {clean_note}"
    return {
        "journal": journal,
        "reflection": "What felt meaningful today? What challenged you? What is one thing you would like to carry into tomorrow?",
        "tasks": pending_tasks,
        "vlog_script": f"Today, {clean_note}",
        "social_caption": "A little memory from today ✨",
        "tomorrow_ideas": [
            "Suggestion: choose one priority for tomorrow.",
            "Suggestion: capture one small moment on video.",
        ],
        "structured_journal": {
            "date": date.today().isoformat(),
            "title": f"{date.today().strftime('%B %d')} journal",
            "opening": f"Today I noticed: {clean_note}",
            "events": [],
            "achievements": [],
            "challenges": [],
            "feelings": [],
            "reflection": "What felt meaningful today?",
            "gratitude": [],
            "closing": "I will carry one useful lesson into tomorrow.",
        },
        "structured_vlog": {
            "title": "A moment from today",
            "hook": "Here is one moment I want to remember.",
            "scenes": ["Opening shot", "Main moment from today's note", "Closing shot"],
            "voiceover": [f"Today, {clean_note}"],
            "b_roll": ["Details of the setting", "Hands or objects connected to the moment"],
            "closing": "That is one moment I want to remember.",
        },
        "structured_social": {
            "caption": "A little memory from today ✨",
            "alternatives": ["One moment I want to keep.", "A quiet note from today."],
            "hashtags": ["#lifelog", "#dailynote"],
            "story_text": clean_note[:180],
        },
        "structured_analogy": {
            "analogy": analogy,
            "mapping": ["The written note is the evidence.", "Unmentioned details stay unknown."],
            "simpler_version": f"You wrote this: {clean_note}",
            "detailed_version": "The analogy only restates what you already recorded; it does not add a new story.",
        },
        "structured_day": {
            "date": date.today().isoformat(),
            "summary": clean_note[:240],
            "events": [],
            "achievements": [],
            "challenges": [],
            "mood": "",
            "completed_tasks": completed_actions,
            "pending_tasks": pending_tasks,
            "future_plans": [],
            "important_moments": [],
            "source_references": ["daily note"],
        },
    }
