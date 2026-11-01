"""A minimal allow-listed tool dispatcher for safe agent/tool-use teaching."""

from __future__ import annotations

from typing import Callable

from .rag import MemoryDocument, answer_from_memories


def run_memory_tool(
    name: str,
    arguments: dict[str, object],
    memories: list[MemoryDocument],
    user_id: int,
) -> dict[str, object]:
    """Expose one read-only, user-scoped memory tool; reject all other tools."""
    if name != "search_memories":
        raise ValueError(f"Tool {name!r} is not allow-listed.")
    question = arguments.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("search_memories requires a non-empty question.")
    raw_ids = arguments.get("selected_ids")
    selected_ids: set[int] | None = None
    if raw_ids is not None:
        if not isinstance(raw_ids, list) or not all(
            isinstance(value, int) and not isinstance(value, bool) for value in raw_ids
        ):
            raise ValueError("selected_ids must be a list of integer memory IDs.")
        selected_ids = set(raw_ids)
    return answer_from_memories(
        memories,
        user_id,
        question,
        selected_ids=selected_ids,
    )


def execute_tool_call(
    name: str,
    arguments: dict[str, object],
    tools: dict[
        str, Callable[[dict[str, object]], dict[str, object]]
    ],
) -> dict[str, object]:
    """Dispatch only to registered callables and surface unknown-tool errors."""
    tool = tools.get(name)
    if tool is None:
        raise ValueError(f"Tool {name!r} is not registered.")
    return tool(arguments)
