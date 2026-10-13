"""Check a link source before you submit to it.

For each target the check reads the site itself (free), then, when the keys are set,
asks GoAnyAPI for its rating, a year of visits and whether Google still lists it, and
AIsa for the spam score of its own backlink profile. Each finding carries the text or
the numbers it came from, so a person can check it.

Cost with both keys: about $0.01 a target (GoAnyAPI) plus about $0.025 for the whole
batch (AIsa). Without keys the page checks still run.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from statistics import mean

from . import UA, aisa, cache, goanyapi, page, updates
from .policy import flag, grade, ranked

WORKERS = 4
EXTRA_PAGES = 3                 # submit, pricing and similar pages read besides the home page
SNIPPET = 160
NEAR = 200                      # how close a price must be to the words that say what is sold
QUOTE_PAD = 30
PARKED_MAX_TEXT = 3000          # a real site that merely writes about parked domains is longer than this
SPAM_NEIGHBORS = 3
SPAM_SCORE_HIGH = 40
CLIFF = 0.6                     # a month under 60% of the month before it
CLIFF_WINDOW = 3                # looked for in the last three months
RECOVERED = 0.7                 # back above 70% of the level before the fall: no longer a cliff
DECLINE = 0.5                   # the last three months against the best earlier three
MIN_LEVEL = 5000                # visits a month; below this a halving is noise
NO_AUDIENCE = 1000              # visits a month
HOLLOW_DR = 60                  # a rating this high ...
HOLLOW_VISITS = 5000            # ... with fewer visits a month than this
REACH_HIGH = 100_000            # visits a month
YOUNG_DAYS = 365
WAYBACK_TIMEOUT = 25
SPAM_TOOL = "post_dataforseo_backlinks_bulk_spam_score_live"
SERP_TOOL = "post_dataforseo_serp_google_organic_live_regular"
US, ENGLISH = 2840, "en"

PARKED = re.compile(r"domain (?:name )?(?:is|may be) for sale|buy this domain|this domain is parked|parked free|"
                    r"domain parking|domain has expired|this domain has been registered|sedoparking|hugedomains|"
                    r"is available for purchase|parked domain", re.I)
SELLS = re.compile(r"do-?follow|backlinks?|link insertion|guest posts?|sponsored (?:posts?|articles?)|write for us|"
                   r"publishing fee|paid (?:posts?|articles?)|article submission", re.I)
PRICE = re.compile(r"[$€£]\s?(?!0(?![.,\d]))\d{1,5}(?:[.,]\d+)?|\b[1-9]\d{0,4}\s?(?:usd|dollars)\b", re.I)   # "$0" is the free tier
EXCHANGE = re.compile(r"reciprocal link|link back to (?:us|our)|backlink to our (?:site|website)|"
                      r"(?:add|place|embed|display|put)\b[^.]{0,60}\b(?:badge|backlink|our link)\b", re.I)
SPAM_WORDS = re.compile(r"\b(?:casino|betting|sportsbook|slots?|poker|porn|escorts?|payday loans?|essay writing|"
                        r"write my essay|replica watches|viagra|cialis|togel|judi|slot gacor)\b", re.I)
LISTING = re.compile(r"\b(?:submit|submission|listing|featured|get listed|review fee)\b", re.I)
SUBPAGE = re.compile(r"submit|pricing|advertis|sponsor|write-?for-?us|guest-?post|list-your|get-listed", re.I)
QUALIFIED = {"nofollow", "sponsored", "ugc"}


def target(raw: str) -> dict:
    url = raw if raw.startswith(("http://", "https://")) else "https://" + raw.strip("/")
    return {"input": raw, "domain": page.site(url), "url": url}


def snippet(text: str, at: int) -> str:
    start = max(0, at - SNIPPET // 2)
    return " ".join(text[start:start + SNIPPET].split())


def priced(text: str, what: re.Pattern) -> str:
    """A passage where `what` sits next to a price, "" when there is none."""
    for m in what.finditer(text):
        offset = max(0, m.start() - NEAR)
        price = PRICE.search(text[offset:m.end() + NEAR])
        if price:                       # quote from the first of the two to the second, so both are in view
            first, last = sorted((m.start(), offset + price.start()))
            return " ".join(text[max(0, first - QUOTE_PAD):last + QUOTE_PAD * 2].split())
    return ""


def read_site(url: str) -> dict:
    """The home page and up to EXTRA_PAGES pages where a site says what it charges."""
    home = page.fetch(url)
    parsed = page.parse(home["html"], home["final"]) if home["html"] else {"title": "", "text": "", "links": []}
    own = page.site(home["final"])
    more, seen = [], {home["final"].rstrip("/")}
    for link in parsed["links"]:
        href = link["href"].split("#")[0].rstrip("/")
        if page.site(href) == own and href not in seen and SUBPAGE.search(href + " " + link["text"]):
            seen.add(href)
            more.append(href)
    with ThreadPoolExecutor(EXTRA_PAGES) as pool:
        extra = [page.parse(p["html"], p["final"]) for p in pool.map(page.fetch, more[:EXTRA_PAGES]) if p["html"]]
    return {"home": home, "parsed": parsed, "texts": [parsed["text"]] + [e["text"] for e in extra]}


def page_flags(read: dict) -> list[dict]:
    home, parsed = read["home"], read["parsed"]
    if home["dead"]:
        return [flag("dead", home["error"] or f"HTTP {home['status']}")]
    if home["blocked"]:
        return [flag("blocked", home["error"])]
    flags = []
    parked = PARKED.search(parsed["text"]) if len(parsed["text"]) < PARKED_MAX_TEXT else None
    if parked:
        flags.append(flag("parked", snippet(parsed["text"], parked.start())))
    sold = next((s for s in (priced(t, SELLS) for t in read["texts"]) if s), "")
    listing = next((s for s in (priced(t, LISTING) for t in read["texts"][1:]) if s), "")   # the submit and pricing pages only
    if sold:
        flags.append(flag("paid_follow", sold))
    elif listing:
        flags.append(flag("paid_listing", listing))
    asked = next((m for m in (EXCHANGE.search(t) for t in read["texts"]) if m), None)
    if asked:
        flags.append(flag("link_exchange", snippet(asked.string, asked.start())))
    bad = [l["href"] for l in page.external(parsed["links"], home["final"]) if SPAM_WORDS.search(l["text"] + " " + l["href"])]
    if len(bad) >= SPAM_NEIGHBORS:
        flags.append(flag("spam_neighbors", f"{len(bad)} such links, e.g. {', '.join(bad[:3])}"))
    return flags


def outbound(read: dict) -> dict:
    links = page.external(read["parsed"]["links"], read["home"]["final"])
    qualified = sum(1 for l in links if l["rel"] & QUALIFIED)
    return {"external_links": len(links), "qualified_share": round(qualified / len(links), 2) if links else None}


def first_seen(domain: str) -> str:
    """The date of the Wayback Machine's first copy, "" when it has none or does not answer."""
    url = "https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode(
        {"url": domain, "limit": 1, "output": "json", "fl": "timestamp"})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=WAYBACK_TIMEOUT) as res:
            rows = json.load(res)       # [["timestamp"], ["20240828075927"]]; an error page is not JSON
    except (OSError, ValueError):
        return ""
    stamp = rows[1][0] if len(rows) > 1 and rows[1] else ""
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}" if len(stamp) >= 8 else ""


def visit_trend(monthly: dict) -> dict:
    """{"now", "earlier", "ratio", "cliff": (month, share kept) or None} from {"2026-09-01": visits}.
    `now` is the last three months on average, `earlier` the best three in a row before them."""
    months = sorted(monthly.items())
    series = [int(v or 0) for _, v in months]
    out = {"now": round(mean(series[-3:])) if series else 0, "earlier": 0, "ratio": None, "cliff": None}
    if len(series) >= 6:
        out["earlier"] = round(max(mean(series[i:i + 3]) for i in range(len(series) - 5)))
        out["ratio"] = round(out["now"] / out["earlier"], 2) if out["earlier"] else None
    for i in range(max(1, len(series) - CLIFF_WINDOW), len(series)):
        before, after = series[i - 1], series[i]
        if before >= MIN_LEVEL and after < before * CLIFF and series[-1] < before * RECOVERED:
            out["cliff"] = (months[i][0][:7], round(after / before, 2))
    return out


def traffic_flags(trend: dict, dr, known: list[dict]) -> list[dict]:
    flags = []
    if trend["cliff"]:
        month, kept = trend["cliff"]
        near = updates.around(month, known)
        flags.append(flag("traffic_cliff", f"{month}: down {round((1 - kept) * 100)}% on the month before"
                          + (f". Google updates around then: {'; '.join(near)}" if near else "")))
    elif trend["ratio"] is not None and trend["ratio"] < DECLINE and trend["earlier"] >= MIN_LEVEL:
        flags.append(flag("traffic_decline", f"{trend['now']:,} a month now, {trend['earlier']:,} earlier in the year"))
    if trend["now"] < NO_AUDIENCE:
        flags.append(flag("no_audience", f"about {trend['now']:,} visits a month"))
    if dr is not None and dr >= HOLLOW_DR and trend["now"] < HOLLOW_VISITS:
        flags.append(flag("hollow_rating", f"rating {dr}, about {trend['now']:,} visits a month"))
    return flags


def paid(source: str, question: str, ask, fresh: bool):
    """(answer, cost): from the cache when it has one, else from `ask()`, which is then stored."""
    key = f"{source}:{question}"
    held = None if fresh else cache.get(key)
    if held is not None:
        return held, 0
    answer, cost = ask()
    cache.put(key, answer)
    return answer, cost


def index_count(domain: str, fresh: bool) -> tuple[int, int]:
    """How many results Google has for site:domain, and the cost. GoAnyAPI first ($0.004);
    when it fails (its search endpoints answered 502 all day on 2026-10-13) the question goes
    to DataForSEO through AIsa ($0.01: a query with a search operator costs five times a plain one)."""
    try:
        data, cost = paid("goanyapi", f"site:{domain}", lambda: goanyapi.call("google-site-search", site=domain), fresh)
        return int(data.get("siteCount") or len(data.get("organic") or [])), cost
    except goanyapi.GoAnyError:
        if not aisa.key():
            raise
    result, cost = paid("aisa", f"site:{domain}", lambda: aisa.call(SERP_TOOL, {
        "keyword": f"site:{domain}", "location_code": US, "language_code": ENGLISH, "depth": 10}), fresh)
    listed = sum(1 for i in result.get("items") or [] if i.get("type") == "organic")
    return int(result.get("se_results_count") or listed), cost


def index_check(domain: str, fresh: bool) -> tuple[int, int]:
    """index_count, asked a second time when the first answer is zero: under load the
    search sources returned nothing for sites with thousands of pages (skills.sh, 10-13)."""
    count, cost = index_count(domain, fresh)
    if count:
        return count, cost
    again, more = index_count(domain, fresh=True)
    return again, cost + more


def market(domain: str, known: list[dict], fresh: bool) -> tuple[dict, list[dict], int, list[str]]:
    """Rating, visits and index status. (metrics, flags, cost, errors)."""
    metrics, flags, cost, errors = {}, [], 0, []
    try:
        data, spent = paid("goanyapi", f"dr:{domain}", lambda: goanyapi.call("dr", domain=domain), fresh)
        metrics["dr"], cost = data.get("domain_rating"), cost + spent
    except goanyapi.GoAnyError as exc:
        errors.append(f"rating: {exc}")
    try:
        data, spent = paid("goanyapi", f"traffic:{domain}", lambda: goanyapi.call("traffic", domain=domain, month=12), fresh)
        trend = visit_trend(data.get("EstimatedMonthlyVisits") or {})
        metrics.update(visits=trend["now"], visits_vs_earlier=trend["ratio"])
        flags += traffic_flags(trend, metrics.get("dr"), known)
        cost += spent
    except goanyapi.GoAnyError as exc:
        errors.append(f"traffic: {exc}")
    if metrics.get("visits", 0) >= MIN_LEVEL:
        return metrics, flags, cost, errors          # a site people reach is listed; the question is not worth asking
    try:
        metrics["indexed"], spent = index_check(domain, fresh)
        cost += spent
        if not metrics["indexed"]:
            flags.append(flag("deindexed", f"site:{domain} returned nothing, asked twice"))
    except (goanyapi.GoAnyError, aisa.AisaError) as exc:
        errors.append(f"index: {exc}")
    return metrics, flags, cost, errors


def reach(metrics: dict) -> str:
    """How many people a listing there can reach: "high", "medium", "low", or "" without data."""
    visits = metrics.get("visits")
    if visits is None:
        return ""
    return "high" if visits >= REACH_HIGH else "low" if visits < NO_AUDIENCE else "medium"


def spam_scores(domains: list[str], fresh: bool) -> tuple[dict[str, int], int]:
    """One call for every domain the cache does not hold."""
    held = {} if fresh else {d: cache.get(f"aisa:spam:{d}") for d in domains}
    scores = {d: v for d, v in held.items() if v is not None}
    missing = [d for d in domains if d not in scores]
    if not missing:
        return scores, 0
    result, cost = aisa.call(SPAM_TOOL, {"targets": missing})
    for item in result.get("items") or []:
        scores[item["target"]] = item.get("spam_score")
        cache.put(f"aisa:spam:{item['target']}", item.get("spam_score"))
    return scores, cost


def vet_one(raw: str, paid_sources: bool, today: date, known: list[dict], fresh: bool) -> dict:
    t = target(raw)
    read = read_site(t["url"])
    flags, metrics, cost, errors = page_flags(read), outbound(read), 0, []
    seen = first_seen(t["domain"])
    metrics["first_seen"] = seen
    if seen and (today - datetime.strptime(seen, "%Y-%m-%d").date()).days < YOUNG_DAYS:
        flags.append(flag("young", f"first archived {seen}"))
    if paid_sources and goanyapi.key():
        more, found, cost, errors = market(t["domain"], known, fresh)
        metrics.update(more)
        flags += found
    if metrics.get("visits", 0) >= NO_AUDIENCE and any(f["flag"] == "dead" for f in flags):
        # People visit it, so it is up: our request failed, the site did not.
        flags = [flag("blocked", f["evidence"]) if f["flag"] == "dead" else f for f in flags]
    return {**t, "title": read["parsed"]["title"][:120], "flags": flags, "metrics": metrics, "cost": cost, "errors": errors}


def vet(targets: list[str], paid_sources: bool = True, today: date | None = None, fresh: bool = False) -> dict:
    """{"rows": [...], "cost": micro-USD, "errors": [...], "sources": {...}}. Rows keep the order given."""
    today = today or date.today()
    known = updates.ranking_updates() if paid_sources and goanyapi.key() else []
    with ThreadPoolExecutor(WORKERS) as pool:
        rows = list(pool.map(lambda raw: vet_one(raw, paid_sources, today, known, fresh), targets))
    cost, errors = sum(r["cost"] for r in rows), [f"{r['domain']}: {e}" for r in rows for e in r["errors"]]
    scores = {}
    if paid_sources and aisa.key():
        try:
            scores, spent = spam_scores(sorted({r["domain"] for r in rows}), fresh)
            cost += spent
        except aisa.AisaError as exc:
            errors.append(f"spam score: {exc}")
    for r in rows:
        score = scores.get(r["domain"])
        r["metrics"]["spam_score"] = score
        if score is not None and score >= SPAM_SCORE_HIGH:
            r["flags"].append(flag("spam_score", f"{score} of 100 (DataForSEO)"))
        r["flags"], r["grade"], r["reach"] = ranked(r["flags"]), grade(r["flags"]), reach(r["metrics"])
    return {"rows": rows, "cost": cost, "errors": errors,
            "sources": {"goanyapi": bool(paid_sources and goanyapi.key()), "aisa": bool(paid_sources and aisa.key())}}
