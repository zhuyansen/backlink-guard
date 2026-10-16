"""The shared list of sites that build or sell spam backlinks, each with public evidence
(github.com/zhuyansen/backlink-spam-list). A site listed there is avoid, with the entry's evidence.
Read once a run and kept a day; free. A list that cannot be read is reported, never read as empty.
The list grows by reports: a check that finds one operator's sites missing from it links to a filled-in report.
"""
from __future__ import annotations

import csv
import io
import os
import urllib.request
from datetime import date
from urllib.parse import quote, urlencode

from . import UA, __version__, cache
from .policy import flag

URL = os.environ.get("BACKLINK_SPAM_LIST_URL", "https://raw.githubusercontent.com/zhuyansen/backlink-spam-list/main/list.csv")
REPORT_FORM = os.environ.get("BACKLINK_SPAM_LIST_REPORT", "https://github.com/zhuyansen/backlink-spam-list/issues/new")
NETWORK = "link-network (one operator's sites - a shared template, redirect, checkout link or account)"   # the form's option
TTL_DAYS = 1
TIMEOUT = 20
REPORT_MIN = 3                  # sites one operator's group needs before it is worth a report
REPORT_SITES = 30               # sites one report carries at most
OPERATOR = {"same_template", "same_owner"}     # findings that only say one operator runs the sites


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


def against(row: dict) -> bool:
    """Something stands against the site besides sharing an operator, which a company's honest sites also do."""
    return any(f["level"] in ("avoid", "caution") and f["flag"] not in OPERATOR for f in row["flags"])


def unlisted(groups: list[dict], rows: list[dict], listed: dict[str, dict] | None, today: date) -> list[dict]:
    """The groups of one operator's sites (vet.shared_templates, vet.shared_owners) worth a report: REPORT_MIN sites
    or more, at least half of those in this check with a finding against them besides the shared operator, and
    some not listed yet. Each with the link to a filled-in report. None when the list could not be read."""
    if listed is None:
        return []
    by_site, out = {r["domain"]: r for r in rows}, []
    for g in groups:
        checked = [d for d in g["sites"] if d in by_site]
        flagged = [d for d in checked if against(by_site[d])]
        missing = [d for d in g["sites"] if d not in listed]
        if len(g["sites"]) >= REPORT_MIN and missing and 2 * len(flagged) >= len(checked):
            out.append({**g, "unlisted": missing, "report": report_url(g, missing, today)})
    return out


def report_url(group: dict, sites: list[str], today: date) -> str:
    """The list's report form, filled in: the first site, the others as members, what they share. Opening it sends
    nothing; the reporter reads it and submits, and a maintainer checks the evidence before anything is listed."""
    shown = sites[:REPORT_SITES]
    shared = (f"{len(group['sites'])} sites share one page title, each site's own name taken out: \"{group['key']}\""
              if group["kind"] == "template" else
              f"{len(group['sites'])} sites report to one analytics or ads account: {group['key']}")
    fields = {"template": "report.yml", "title": f"Report: {shown[0]}" + (f" and {len(shown) - 1} more" if len(shown) > 1 else ""),
              "domain": shown[0], "category": NETWORK, "evidence-url": f"https://{shown[0]}/", "evidence": shared,
              "members": "\n".join(shown[1:]),
              "context": f"Found with backlink-guard {__version__} on {today.isoformat()}: the sites came up in checks together."}
    return f"{REPORT_FORM}?{urlencode(fields, quote_via=quote)}"
