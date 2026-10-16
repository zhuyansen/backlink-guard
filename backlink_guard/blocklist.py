"""The shared list of sites that build or sell spam backlinks, each with public evidence
(github.com/zhuyansen/backlink-spam-list). A site listed there is avoid, with the entry's evidence.
Read once a run and kept a day; free. A list that cannot be read is reported, never read as empty.
"""
from __future__ import annotations

import csv
import io
import os
import urllib.request

from . import UA, cache
from .policy import flag

URL = os.environ.get("BACKLINK_SPAM_LIST_URL", "https://raw.githubusercontent.com/zhuyansen/backlink-spam-list/main/list.csv")
TTL_DAYS = 1
TIMEOUT = 20


def load(fresh: bool = False) -> dict[str, dict]:
    """{domain: entry} for the entries still listed. Raises OSError or ValueError when the list cannot be read."""
    held = None if fresh else cache.get(f"spamlist:{URL}", ttl_days=TTL_DAYS)
    if held is not None:
        return held
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": UA}), timeout=TIMEOUT) as res:
        text = res.read().decode("utf-8")
    rows = csv.DictReader(io.StringIO(text))
    held = {r["domain"]: {k: r.get(k, "") for k in ("category", "family", "evidence", "evidence_url", "last_checked")}
            for r in rows if r.get("status") == "listed"}
    cache.put(f"spamlist:{URL}", held)
    return held


def flag_for(domain: str, listed: dict[str, dict]) -> dict | None:
    e = listed.get(domain)
    if not e:
        return None
    family = f", the {e['family']} family" if e.get("family") else ""
    return flag("listed", f"{e['category']}{family}: {e['evidence'][:180]} ({e['evidence_url']}, checked {e['last_checked']})")
