"""A record of what you submitted where, so the pace and the anchors can be checked
before the next one. One JSON object a line in <state>/ledger.jsonl; nothing leaves the machine.

The limits are the ones Agent Skills Hub worked to in 2026: a handful of submissions a
week, one pull request per list, and anchor text that changes from place to place.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from . import state_dir
from .policy import flag

KINDS = ("directory", "awesome-list", "guest-post", "community", "registry", "other")
STATUSES = ("submitted", "live", "rejected", "dropped")
WEEKLY_LIMIT = 5
ANCHOR_SHARE = 0.5
ANCHOR_MIN = 4


def path() -> Path:
    return state_dir() / "ledger.jsonl"


def entries() -> list[dict]:
    if not path().exists():
        return []
    return [json.loads(line) for line in path().read_text().splitlines() if line.strip()]


def save(rows: list[dict]) -> None:
    path().parent.mkdir(parents=True, exist_ok=True)
    path().write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def add(target: str, kind: str, anchor: str = "", paid: float = 0.0, url: str = "", note: str = "",
        today: date | None = None) -> dict:
    row = {"date": (today or date.today()).isoformat(), "target": target, "kind": kind, "anchor": anchor,
           "paid": paid, "url": url, "status": "submitted", "note": note}
    save(entries() + [row])
    return row


def update(target: str, **changes) -> dict | None:
    """Change the latest entry for `target`. Returns it, or None when there is none."""
    rows = entries()
    for row in reversed(rows):
        if row["target"] == target:
            row.update({k: v for k, v in changes.items() if v not in (None, "")})
            save(rows)
            return row
    return None


def checks(rows: list[dict], today: date | None = None, limit: int = WEEKLY_LIMIT) -> list[dict]:
    """Flags on the record itself: too many this week, or one anchor used again and again."""
    today, flags = today or date.today(), []
    week = [r for r in rows if r["date"] > (today - timedelta(days=7)).isoformat()]
    if len(week) > limit:
        flags.append(flag("pace", f"{len(week)} submissions in the last 7 days; your limit is {limit}"))
    anchors = Counter(r["anchor"].strip().lower() for r in rows if r.get("anchor", "").strip())
    if anchors and sum(anchors.values()) >= ANCHOR_MIN:
        text, n = anchors.most_common(1)[0]
        if n / sum(anchors.values()) >= ANCHOR_SHARE:
            sites = len({r["target"] for r in rows if r.get("anchor", "").strip().lower() == text})
            flags.append(flag("anchor_repeat", f"\"{text}\" used for {n} of {sum(anchors.values())} submissions, "
                                               f"on {sites} site{'s' if sites != 1 else ''}"))
    return flags
