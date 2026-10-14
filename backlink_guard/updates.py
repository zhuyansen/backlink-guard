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

# The feed holds only the last nine incidents. The ones before, from the dashboard's history
# page (https://status.search.google.com/products/rGHU1u87FJnkP6W2GwMi/history, read
# 2026-10-14), so a fall years back can be read too. Ends are begin plus the listed duration.
EARLIER = (
    ("September 2026 spam update", "2026-09-24", "2026-10-07"),
    ("August 2026 spam update", "2026-08-18", "2026-08-20"),
    ("June 2026 spam update", "2026-06-24", "2026-06-26"),
    ("May 2026 core update", "2026-05-21", "2026-06-01"),
    ("March 2026 core update", "2026-03-27", "2026-04-08"),
    ("March 2026 spam update", "2026-03-24", "2026-03-24"),
    ("February 2026 Discover update", "2026-02-05", "2026-02-26"),
    ("December 2025 core update", "2025-12-11", "2025-12-29"),
    ("August 2025 spam update", "2025-08-26", "2025-09-21"),
    ("June 2025 core update", "2025-06-30", "2025-07-16"),
    ("March 2025 core update", "2025-03-13", "2025-03-26"),
    ("December 2024 spam update", "2024-12-19", "2024-12-26"),
    ("December 2024 core update", "2024-12-12", "2024-12-18"),
    ("November 2024 core update", "2024-11-11", "2024-12-04"),
    ("August 2024 core update", "2024-08-15", "2024-09-03"),
    ("June 2024 spam update", "2024-06-20", "2024-06-27"),
    ("March 2024 spam update", "2024-03-05", "2024-03-19"),
    ("March 2024 core update", "2024-03-05", "2024-04-19"),
    ("November 2023 reviews update", "2023-11-08", "2023-12-07"),
    ("November 2023 core update", "2023-11-02", "2023-11-27"),
    ("October 2023 core update", "2023-10-05", "2023-10-18"),
    ("October 2023 spam update", "2023-10-04", "2023-10-19"),
    ("September 2023 helpful content update", "2023-09-14", "2023-09-27"),
    ("August 2023 core update", "2023-08-22", "2023-09-07"),
    ("April 2023 reviews update", "2023-04-12", "2023-04-25"),
    ("March 2023 core update", "2023-03-15", "2023-03-28"),
    ("February 2023 product reviews update", "2023-02-21", "2023-03-07"),
    ("December 2022 link spam update", "2022-12-14", "2023-01-12"),
    ("December 2022 helpful content update", "2022-12-05", "2023-01-12"),
    ("October 2022 spam update", "2022-10-19", "2022-10-21"),
    ("September 2022 product reviews update", "2022-09-20", "2022-09-26"),
    ("September 2022 core update", "2022-09-12", "2022-09-26"),
    ("August 2022 helpful content update", "2022-08-25", "2022-09-09"),
    ("July 2022 product reviews update", "2022-07-27", "2022-08-02"),
    ("May 2022 core update", "2022-05-25", "2022-06-09"),
    ("March 2022 product reviews update", "2022-03-23", "2022-04-06"),
    ("Page experience update for desktop", "2022-02-22", "2022-03-03"),
    ("December 2021 product reviews update", "2021-12-01", "2021-12-21"),
    ("November 2021 core update", "2021-11-17", "2021-11-30"),
    ("November 2021 spam update", "2021-11-03", "2021-11-11"),
)


def ranking_updates() -> list[dict]:
    """[{"name", "begin", "end"}] newest first: the live feed, then the earlier list for what it lacks."""
    cached = cache.get(FEED, ttl_days=1)
    if cached is not None:
        return cached
    try:
        with urllib.request.urlopen(urllib.request.Request(FEED, headers={"User-Agent": UA}), timeout=20) as res:
            feed = json.load(res)
    except (OSError, ValueError):
        feed = None
    rows = [{"name": i.get("external_desc", ""), "begin": (i.get("begin") or "")[:10], "end": (i.get("end") or "")[:10]}
            for i in feed or [] if any(p.get("title") == "Ranking" for p in i.get("affected_products") or [])]
    live = {r["name"] for r in rows}
    rows += [{"name": n, "begin": b, "end": e} for n, b, e in EARLIER if n not in live]
    rows.sort(key=lambda r: r["begin"], reverse=True)
    if feed is not None:
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
