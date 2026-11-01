"""Local, user-scoped retrieval and extractive answers over selected memories."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from math import log, sqrt
from pathlib import Path


TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z'-]*")
STOP_WORDS = {
    "about", "after", "again", "from", "have", "that", "the", "this", "what",
    "when", "where", "which", "with", "would", "your",
}


@dataclass(frozen=True)
class MemoryDocument:
    memory_id: int
    user_id: int
    memory_date: str
    text: str


@dataclass(frozen=True)
class RetrievedMemory:
    memory: MemoryDocument
    score: float
    excerpt: str


def _tokens(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_PATTERN.findall(text)
        if len(token) > 2 and token.lower() not in STOP_WORDS
    ]


def _excerpt(text: str, query_tokens: set[str]) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    ranked = sorted(
        enumerate(sentences),
        key=lambda item: (
            len(query_tokens.intersection(_tokens(item[1]))),
            -item[0],
        ),
        reverse=True,
    )
    if not ranked or not query_tokens.intersection(_tokens(ranked[0][1])):
        return text.strip()[:500]
    return ranked[0][1].strip()[:500]


def retrieve_memories(
    memories: list[MemoryDocument],
    user_id: int,
    question: str,
    selected_ids: set[int] | None = None,
    limit: int = 3,
) -> list[RetrievedMemory]:
    """Filter ownership before ranking; selected IDs never bypass the user check."""
    if limit < 1:
        raise ValueError("Retrieval limit must be positive.")
    query_tokens = set(_tokens(question))
    if not query_tokens:
        return []
    eligible = [
        memory
        for memory in memories
        if memory.user_id == user_id
        and (selected_ids is None or memory.memory_id in selected_ids)
    ]
    documents = [(memory, set(_tokens(memory.text))) for memory in eligible]
    document_frequency = {
        token: sum(token in words for _, words in documents)
        for token in query_tokens
    }
    results: list[RetrievedMemory] = []
    for memory, words in documents:
        weighted = {
            token: (1 + log((1 + len(documents)) / (1 + document_frequency[token])))
            for token in query_tokens.intersection(words)
        }
        numerator = sum(weighted.values())
        denominator = sqrt(sum(value * value for value in weighted.values()))
        score = numerator / denominator if denominator else 0.0
        if score:
            results.append(
                RetrievedMemory(
                    memory=memory,
                    score=score,
                    excerpt=_excerpt(memory.text, query_tokens),
                )
            )
    return sorted(results, key=lambda item: item.score, reverse=True)[:limit]


def answer_from_memories(
    memories: list[MemoryDocument],
    user_id: int,
    question: str,
    selected_ids: set[int] | None = None,
) -> dict[str, object]:
    retrieved = retrieve_memories(memories, user_id, question, selected_ids)
    if not retrieved:
        return {
            "answer": "I couldn't find that detail in the selected memories.",
            "citations": [],
        }
    citations = [
        {
            "memory_id": result.memory.memory_id,
            "date": result.memory.memory_date,
            "score": round(result.score, 4),
        }
        for result in retrieved
    ]
    answer = "\n".join(
        f'- "{result.excerpt}" [{result.memory.memory_date}]'
        for result in retrieved
    )
    return {"answer": answer, "citations": citations}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default="What did I do in the garden?")
    parser.add_argument("--user-id", type=int, default=10)
    parser.add_argument("--selected-ids", type=int, nargs="*")
    args = parser.parse_args()
    sample_path = Path(__file__).parent / "sample_data" / "notes.json"
    with sample_path.open(encoding="utf-8") as source:
        rows = json.load(source)
    memories = [
        MemoryDocument(
            memory_id=row["memory_id"],
            user_id=row["user_id"],
            memory_date=row["date"],
            text=row["text"],
        )
        for row in rows
    ]
    result = answer_from_memories(
        memories,
        args.user_id,
        args.question,
        set(args.selected_ids) if args.selected_ids is not None else None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
