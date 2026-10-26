"""The backlink, search and keyword data: through Glasser when GLASSER_API_KEY is set, else through AIsa.

Both resell the same endpoints, at the same prices but for two searches (glasser.py), so an answer is the
same data whichever was asked, and it is cached under the one name vet.paid gives it ("aisa:"). Ahrefs'
rating and Semrush's numbers (--deep), searches with operators (site:) and the AI answers of `questions`
and `asked` stay on AIsa: Glasser does not sell them.
"""
from __future__ import annotations

from . import aisa, glasser


def key() -> str:
    """The key these calls will use, or "" when there is neither."""
    return glasser.key() or aisa.key()


def name() -> str:
    """Who answers, for the evidence a report shows: "Glasser" or "AIsa"."""
    return "Glasser" if glasser.key() else "AIsa"


def call(tool: str, body: dict) -> tuple[dict, int]:
    """One task: (its first result, cost in micro-USD). An empty result raises, as aisa.call does."""
    return glasser.call(tool, body) if glasser.key() else aisa.call(tool, body)


def rest(path: str, body: dict) -> tuple[dict, int]:
    """One passthrough task: (its first result or {}, cost in micro-USD)."""
    return glasser.rest(path, body) if glasser.key() else aisa.rest(path, body)
