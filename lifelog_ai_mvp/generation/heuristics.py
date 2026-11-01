import re


TASK_MARKERS = (
    "need to ", "have to ", "must ", "should ", "remember to ",
    "plan to ", "going to ", "todo:", "to-do:",
)
COMPLETED_MARKERS = ("finished ", "completed ", "did ", "already ")


def _sentences(note):
    for sentence in re.split(r"(?<=[.!?])\s+|[;\n]+", note):
        clean_sentence = " ".join(sentence.split()).strip(" -")
        if clean_sentence:
            yield clean_sentence


def _next_marker_index(text, markers, start):
    indices = [
        index
        for marker in markers
        if (index := text.find(marker, start)) >= 0
    ]
    return min(indices) if indices else len(text)


def extract_pending_tasks(note):
    """Lightweight fallback when no LLM is configured."""
    candidates = []
    for clean_sentence in _sentences(note):
        lowered = clean_sentence.lower()
        for marker in TASK_MARKERS:
            marker_index = lowered.find(marker)
            if marker_index >= 0:
                task = clean_sentence[marker_index + len(marker):].strip(" .,!?:")
                if task and task not in candidates:
                    candidates.append(task[0].upper() + task[1:])
                break
    return candidates


def extract_completed_actions(note):
    actions = []
    for clean_sentence in _sentences(note):
        lowered = clean_sentence.lower()
        for marker in COMPLETED_MARKERS:
            marker_index = lowered.find(marker)
            if marker_index >= 0:
                action_start = marker_index + len(marker)
                action_end = _next_marker_index(lowered, TASK_MARKERS, action_start)
                action = clean_sentence[action_start:action_end].strip(" .,!?:;")
                action = re.sub(r"\s+(and|but|so|then)$", "", action, flags=re.IGNORECASE)
                if action and action not in actions:
                    actions.append(action[0].upper() + action[1:])
                break
    return actions
