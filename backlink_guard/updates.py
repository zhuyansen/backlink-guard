"""Google's own list of ranking updates (https://status.search.google.com), so a drop in
a site's visits can be read next to the updates that ran around it. Being next to an
update is context, not a cause: the tool never says an update hit a site."""
from __future__ import annotations

import json
import urllib.request
from datetime import date, timedelta

from . import UA, cache

FEED = "https://status.search.google.com/incidents.json"
LOOK_BACK = timedelta(days=45)     # an update that ended this long before a month can still show in it


def ranking_updates() -> list[dict]:
    """[{"name", "begin", "end"}] newest first; [] when the feed cannot be read."""
    cached = cache.get(FEED, ttl_days=1)
    if cached is not None:
        return cached
    try:
        with urllib.request.urlopen(urllib.request.Request(FEED, headers={"User-Agent": UA}), timeout=20) as res:
            feed = json.load(res)
    except (OSError, ValueError):
        return []
    rows = [{"name": i.get("external_desc", ""), "begin": (i.get("begin") or "")[:10], "end": (i.get("end") or "")[:10]}
            for i in feed if any(p.get("title") == "Ranking" for p in i.get("affected_products") or [])]
    rows.sort(key=lambda r: r["begin"], reverse=True)
    cache.put(FEED, rows)
    return rows


def around(month: str, updates: list[dict]) -> list[str]:
    """Names of the updates that ran during `month` ("2026-09") or shortly before it."""
    first = date.fromisoformat(month + "-01")
    last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    hits = []
    for u in updates:
        if not u["begin"]:
            continue
        begin, end = date.fromisoformat(u["begin"]), date.fromisoformat(u["end"] or u["begin"])
        if begin <= last and end >= first - LOOK_BACK:
            hits.append(f"{u['name']} ({u['begin']} to {u['end'] or 'ongoing'})")
    return hits
