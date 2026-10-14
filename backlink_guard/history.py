"""Has the site lost its Google search traffic before, and when?

DataForSEO's monthly estimate of each site's US Google organic traffic and ranking keywords,
through AIsa: one call for every site of a run, about $0.12 a call plus $0.0012 a site (seen
2026-10-14). The months run from January 2022: that December the whole database moved, seven
in ten sites "falling" more than 60% in one month.

Two kinds of fall in this data are not the site's doing, and the check takes both out:
- the database shifts. In November 2024 the median site fell 46% and came back the month
  after. Twelve large, steady sites ride along in every call, and each month is divided by
  their median change.
- one site's estimate jumps a hundredfold for a few months and drops back: mcpmarket.com went
  from 10 thousand to 3.4 million in a month in 2026 while Semrush showed steady growth. One
  huge keyword misread; the site's ranking keywords never moved. So a fall counts only when
  the keywords fall with the traffic.

A fall next to a Google update is context, not proof that the update did it.
"""
from __future__ import annotations

from datetime import date
from statistics import median

from . import aisa, cache, updates
from .policy import flag

TOOL = "post_dataforseo_labs_google_historical_bulk_traffic_live"
US, START = 2840, "2022-01-01"
MAX_TARGETS = 1000              # sites a call takes
CONTROLS = ("wikipedia.org", "github.com", "stackoverflow.com", "medium.com", "dev.to", "reddit.com",
            "quora.com", "nytimes.com", "bbc.com", "imdb.com", "apple.com", "mozilla.org")
MIN_BEFORE = 100                # search visits a month before a fall; below this a fall is noise
KEPT = 0.4                      # traffic left, two months running
KEPT_KEYWORDS = 0.6             # ranking keywords left: traffic alone falling is the misread-keyword case
RECOVERED = 0.5                 # back above half the level before: not a fall any more
RECENT_MONTHS = 12              # a fall this recent is a caution; an older one is a note
SCALED_PAGES = 1000             # pages a site's sitemaps list before the ratio below means anything
SCALED_RATIO = 1000             # pages listed for each keyword the site ranks for on US Google


def months(item: dict) -> dict:
    """{"2026-09": [traffic, keywords]} from one DataForSEO item."""
    return {f"{p['year']}-{p['month']:02d}": [p.get("etv") or 0, p.get("count") or 0]
            for p in (item.get("metrics") or {}).get("organic") or []}


def series(domains: list[str], fresh: bool) -> tuple[dict, int]:
    """{domain: months} for the domains and the controls, buying only what the cache lacks."""
    wanted = sorted(set(domains) | set(CONTROLS))
    held = {} if fresh else {d: cache.get(f"aisa:history:{d}") for d in wanted}
    data = {d: v for d, v in held.items() if v is not None}
    missing, cost = [d for d in wanted if d not in data], 0
    for i in range(0, len(missing), MAX_TARGETS):
        asked = missing[i:i + MAX_TARGETS]
        result, spent = aisa.call(TOOL, {"targets": asked, "location_code": US, "language_code": "en",
                                         "date_from": START, "item_types": ["organic"]})
        cost += spent
        got = {item["target"]: months(item) for item in result.get("items") or []}
        for d in asked:
            data[d] = got.get(d, {})
            cache.put(f"aisa:history:{d}", data[d])
    return data, cost


def index(data: dict) -> dict:
    """The database's own level each month, from the controls' median change; the first month is 1."""
    keys = sorted({m for c in CONTROLS for m in data.get(c, {})})
    level = {}
    for prev, m in zip([None, *keys], keys):
        changes = [data[c][m][0] / data[c][prev][0] for c in CONTROLS
                   if prev and data.get(c, {}).get(prev, [0])[0] and m in data[c]]
        level[m] = level[prev] * median(changes) if prev and changes else level.get(prev, 1.0)
    return level


def falls(monthly: dict, level: dict) -> list[dict]:
    """Falls that held two months, took the keywords with them and have not come back; oldest first."""
    level = level or dict.fromkeys(monthly, 1.0)      # no controls came back: read the site as it is
    keys = sorted(m for m in monthly if m in level)
    raw = [monthly[m][0] for m in keys]
    rel = [r / level[m] if level[m] else 0 for r, m in zip(raw, keys)]
    words = [monthly[m][1] for m in keys]
    found = []
    for i in range(2, len(keys) - 1):
        before, after, since = max(rel[i - 2:i]), max(rel[i:i + 2]), max(rel[max(i + 1, len(rel) - 2):])
        words_before, words_after = max(words[i - 2:i]), min(words[i:i + 2])
        if (max(raw[i - 2:i]) < MIN_BEFORE or after > before * KEPT or since > before * RECOVERED
                or words_after > words_before * KEPT_KEYWORDS):
            continue
        if found and keys.index(found[-1]["month"]) >= i - 2:
            continue                                  # the same fall, seen again a month later
        found.append({"month": keys[i], "before": round(max(raw[i - 2:i])), "after": round(max(raw[i:i + 2])),
                      "keywords": [words_before, words_after]})
    return found


def flags_for(monthly: dict, level: dict, today: date, known: list[dict]) -> tuple[dict, list[dict]]:
    """(metrics, flags) for one site."""
    metrics = {"search_visits": round(monthly[max(monthly)][0]) if monthly else None}
    found = falls(monthly, level)
    if not found:
        return metrics, []
    last = found[-1]
    year, month = map(int, last["month"].split("-"))
    age = (today.year - year) * 12 + today.month - month
    near = updates.around(last["month"], known)
    text = (f"US Google, DataForSEO estimate: about {last['before']:,} search visits a month before {last['month']},"
            f" {last['after']:,} after; ranking keywords {last['keywords'][0]:,} to {last['keywords'][1]:,}"
            + (f". Google updates around then: {'; '.join(near)}" if near else "")
            + (f". Earlier falls: {', '.join(f['month'] for f in found[:-1])}" if len(found) > 1 else ""))
    metrics["search_fall"] = last["month"]
    return metrics, [flag("search_fall" if age <= RECENT_MONTHS else "old_search_fall", text)]


def scaled(pages: int | None, words: int | None, lang: str | None) -> list[dict]:
    """Thousands of pages listed and almost none ranking: on 90 Ahrefs-labelled sites, 10 of the 14 with
    1,000 or more pages per ranking keyword were marked spam (2026-10-14). US rankings say little about a
    site written in another language, so those are left alone."""
    if not pages or pages < SCALED_PAGES or words is None or (lang and not lang.startswith("en")):
        return []
    per = pages / max(words, 1)
    if per < SCALED_RATIO:
        return []
    return [flag("scaled_pages", f"its sitemaps list {pages:,} or more pages; it ranks for {words:,} keywords on US Google "
                                 f"(DataForSEO), about {round(per):,} pages for each")]


def check(rows: list[dict], today: date, known: list[dict], fresh: bool) -> int:
    """Adds each row's search history to its metrics and flags; returns the cost."""
    data, cost = series(sorted({r["domain"] for r in rows}), fresh)
    level = index(data)
    for r in rows:
        monthly = data.get(r["domain"]) or {}
        metrics, found = flags_for(monthly, level, today, known)
        metrics["ranking_keywords"] = monthly[max(monthly)][1] if monthly else None
        r["metrics"].update(metrics)
        r["flags"] += found + scaled(r["metrics"].get("pages_listed"), metrics["ranking_keywords"], r["metrics"].get("lang"))
    return cost
