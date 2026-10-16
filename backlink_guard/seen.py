"""Page templates and analytics accounts from earlier checks, so a site checked on its own is still matched against
the networks seen before: one operator's sites rarely come up in the same check. Kept in <state>/seen.json, on this
machine only; a site not seen again with a template or an account for KEEP_DAYS is dropped from it."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from . import state_dir

KEEP_DAYS = 365
KINDS = ("templates", "ids")


def path() -> Path:
    return state_dir() / "seen.json"


def load() -> dict[str, dict[str, dict[str, str]]]:
    """{"templates": {template: {site: last seen}}, "ids": {account: {site: last seen}}}; empty when there is none."""
    try:
        data = json.loads(path().read_text())
    except (OSError, ValueError):
        data = {}
    return {kind: data.get(kind, {}) for kind in KINDS}


def record(seen: dict, kind: str, keys: dict[str, list[str]], today: date) -> None:
    """Add this run's {key: [sites]} and drop what was last seen more than KEEP_DAYS ago."""
    for key, sites in keys.items():
        for site in sites:
            seen[kind].setdefault(key, {})[site] = today.isoformat()
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    for key in list(seen[kind]):
        seen[kind][key] = {site: when for site, when in seen[kind][key].items() if when >= cutoff}
        if not seen[kind][key]:
            del seen[kind][key]


def save(seen: dict) -> None:
    path().parent.mkdir(parents=True, exist_ok=True)
    temp = path().with_suffix(".tmp")
    temp.write_text(json.dumps(seen, indent=1, sort_keys=True))
    temp.replace(path())
