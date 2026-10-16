"""Look again at the sites you already have links on, and say what changed since the last look.

The ledger lists where you submitted. Checked again (vet) now and then, a site that has since been
dropped by Google, parked, hacked or folded into a network shows up, and with your domain given, so
does a link of yours that is gone (verify, free). Each look is kept in <state>/recheck.json; the next
one is compared with it. Monthly is enough: with a dozen sites it costs a few cents.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from . import ledger, verify, vet

WATCHED = ("submitted", "live")
WORSE = {"ok": 0, "incomplete": 0, "caution": 1, "avoid": 2}


def path() -> Path:
    return Path(os.environ.get("BACKLINK_GUARD_STATE", "state")) / "recheck.json"


def last() -> dict:
    return json.loads(path().read_text()) if path().exists() else {}


def sites(entries: list[dict]) -> list[str]:
    """The sites of the entries still standing, once each, newest first."""
    return list(dict.fromkeys(e["target"] for e in reversed(entries) if e.get("status") in WATCHED))


def links(entries: list[dict], own: str) -> dict[str, str]:
    """{page url: verdict} for the entries that recorded where the link sits."""
    return {e["url"]: verify.verify(e["url"], own)["verdict"] for e in entries
            if e.get("status") in WATCHED and e.get("url")}


def changes(before: dict, now: dict) -> list[str]:
    """What got worse between two looks: a lower grade, a new finding against the site, a link gone."""
    out = []
    for site, n in now.get("sites", {}).items():
        b = before.get("sites", {}).get(site)
        if not b:
            continue
        if WORSE[n["grade"]] > WORSE[b["grade"]]:
            out.append(f"{site}: {b['grade']} -> {n['grade']}")
        new = sorted(set(n["flags"]) - set(b["flags"]))
        if new:
            out.append(f"{site}: new {', '.join(new)}")
    for url, verdict in now.get("links", {}).items():
        was = before.get("links", {}).get(url)
        if was and was != verdict:
            out.append(f"{url}: link {was} -> {verdict}")
    return out


def run(own: str = "", paid_sources: bool = True, deep: bool = False, fresh: bool = False, today: date | None = None) -> dict:
    entries = ledger.entries()
    targets = sites(entries)
    checked = vet.vet(targets, paid_sources=paid_sources, today=today, fresh=fresh, deep=deep) if targets else \
        {"rows": [], "cost": 0, "errors": [], "sources": {}}
    now = {"date": (today or date.today()).isoformat(),
           "sites": {r["domain"]: {"grade": r["grade"], "flags": [f["flag"] for f in r["flags"] if f["level"] != "note"]}
                     for r in checked["rows"]},
           "links": links(entries, own) if own else {}}
    before = last()
    found = changes(before, now)
    path().parent.mkdir(parents=True, exist_ok=True)
    path().write_text(json.dumps(now, ensure_ascii=False, indent=1))
    return {**now, "previous": before.get("date", ""), "changes": found, "vet": checked}
