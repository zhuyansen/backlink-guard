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
from datetime import date, datetime, timedelta
from statistics import mean

from . import UA, aisa, cache, goanyapi, history, page, updates
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
HOLLOW_DR = 30                  # a rating this high ... (60 until 10-14: the link-network sites on
                                # a paid list of "top AI-site backlink sources" sat at 36-49 with under 2,500 visits)
HOLLOW_VISITS = 5000            # ... with fewer visits a month than this
REACH_HIGH = 100_000            # visits a month
YOUNG_DAYS = 365
WAYBACK_TIMEOUT = 25
RECENT_DAYS = 30
ACTIVE_MIN = 5                  # pages a sitemap must show as changed before "Google takes none" means anything
SITEMAPS = 6                    # sitemap files read at most
SPAM_TOOL = "post_dataforseo_backlinks_bulk_spam_score_live"
SUMMARY_TOOL = "post_dataforseo_backlinks_summary_live"
TEMPLATE_PLACES = ("footer", "nav", "header", "aside")
BADGE_MIN_DOMAINS = 21
BADGE_LINKS_PER_DOMAIN = 100
BADGE_TEMPLATE_SHARE = 0.3
BADGE_MAX_NOFOLLOW = 0.15
UNPROVEN_DAYS = 365
UNPROVEN_DOMAINS = 100
SERP_TOOL = "post_dataforseo_serp_google_organic_live_regular"
US, ENGLISH = 2840, "en"

PARKED = re.compile(r"domain (?:name )?(?:is|may be) for sale|buy this domain|this domain is parked|parked free|"
                    r"domain parking|domain has expired|this domain has been registered|sedoparking|hugedomains|"
                    r"is available for purchase|parked domain", re.I)
SELLS = re.compile(r"do-?follow|backlinks?|link insertion|guest posts?|sponsored (?:posts?|articles?)|write for us|"
                   r"publishing fee|paid (?:posts?|articles?)|article submission", re.I)
PRICE = re.compile(r"[$€£]\s?(?!0(?![.,\d]))\d{1,5}(?:[.,]\d+)?|\b[1-9]\d{0,4}\s?(?:usd|dollars)\b", re.I)   # "$0" is the free tier
# "Our badge on your site", not any badge: v2ex's "display a PRO badge next to your username" is not an exchange.
EXCHANGE = re.compile(r"reciprocal link|link back to (?:us|our)|backlink to our (?:site|website)|"
                      r"(?:add|place|embed|display|put)\b[^.]{0,30}\bour (?:dofollow )?(?:badge|backlink|link|widget)\b|"
                      r"(?:add|place|embed|display|put)\b[^.]{0,40}\b(?:badge|backlink)\b[^.]{0,40}\b(?:on|to) (?:your|my) "
                      r"(?:site|website|homepage)\b|if you (?:are happy to )?add (?:a|an|our) [\w.]+ (?:badge|backlink)", re.I)
# A site whose business is selling links says so in its title: "Premium DR, DA, TF, PBN & Guest Posts".
LINK_SELLER = re.compile(r"\bpbn\b|\b(?:dr|da)\b[^|]{0,12}\b(?:da|tf|dr)\b[^|]{0,20}\b(?:pbn|backlinks?|guest)|"
                         r"\bbuy (?:dofollow |quality )?backlinks?\b|\bbacklinks? (?:service|package|shop)s?\b", re.I)
SPAM_WORDS = re.compile(r"\b(?:casino|betting|sportsbook|slots?|poker|porn|escorts?|payday loans?|essay writing|"
                        r"write my essay|replica watches|viagra|cialis|togel|judi|slot gacor)\b", re.I)
LISTING = re.compile(r"\b(?:submit|submission|listing|featured|get listed|review fee)\b", re.I)
# Seen on 2026-10-14 among the most-cited sources of a paid backlink list: dozens of sites titled
# "URL Shortener" or "<domain> | Keyword Rankingss", built to be submitted to in bulk.
SHORTENER = re.compile(r"\b(?:url|link) shortener\b|\bshorten (?:your )?(?:long )?(?:urls?|links?)\b", re.I)
LINK_FARM = re.compile(r"\|\s*keyword rankings{1,2}\b|free domain sharing|site not yet configured", re.I)
TEMPLATE_MIN = 12               # characters a shared title needs before it says anything
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
    title = parsed["title"]
    if LINK_FARM.search(title):
        flags.append(flag("link_farm", f"title: \"{title[:80]}\""))
    elif SHORTENER.search(title):         # the title only: directories list shorteners among their tools
        flags.append(flag("shortener", f"title: \"{title[:80]}\""))
    if LINK_SELLER.search(title):
        flags.append(flag("link_seller", f"title: \"{title[:80]}\""))
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


def recent_count(domain: str, window: str, fresh: bool) -> tuple[int, str, int]:
    """(results Google has for site:domain from the last week "w" or month "m", the newest result's
    date as Google words it, cost). A failure raises: it is never a zero."""
    data, cost = paid("goanyapi", f"recent:{window}:{domain}",
                      lambda: goanyapi.call("google-site-search", site=domain, qdr=window), fresh)
    found = data.get("organic") or []
    newest = next((e.get("text", "") for o in found for e in o.get("extensions") or [] if e.get("text")), "")
    count = data.get("siteCount")
    return (int(count) if count is not None else len(found)), newest, cost


def site_activity(domain: str, today: date) -> int | None:
    """URLs the site's own sitemaps say changed in the last 30 days, None when it has no readable sitemap.
    Reads robots.txt for the sitemaps, follows an index one level down, at most SITEMAPS files."""
    robots = page.fetch(f"https://{domain}/robots.txt")
    maps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots["html"]) or [f"https://{domain}/sitemap.xml"]
    stamps, read = [], 0
    while maps and read < SITEMAPS:
        got = page.fetch(maps.pop(0))
        read += 1
        if got["dead"] or got["blocked"]:
            continue
        if "<sitemapindex" in got["html"]:
            maps += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", got["html"])[:SITEMAPS]
        stamps += re.findall(r"<lastmod>\s*(\d{4}-\d{2}-\d{2})", got["html"])
    if not stamps:              # no sitemap, or one without dates: activity unknown
        return None
    since = (today - timedelta(days=RECENT_DAYS)).isoformat()
    return sum(1 for d in stamps if d >= since)


def recent_flags(domain: str, today: date, fresh: bool) -> tuple[dict, list[dict], int, list[str]]:
    """Whether Google is taking in the site's new pages: the friend-of-a-friend check "no page indexed
    in the last week means a paid post there will not be either", made safer. Google's own words: a
    site: search is not a full count, and new pages take days to weeks. So: a week and a month are both
    asked, a zero is asked twice, a failure is a failure, and the site's sitemap says whether there were
    new pages to index at all."""
    metrics, cost, errors = {}, 0, []
    for window, key in (("w", "indexed_week"), ("m", "indexed_month")):
        try:
            count, newest, spent = recent_count(domain, window, False)
            if not count:
                count, newest, more = recent_count(domain, window, True)
                spent += more
            metrics[key], cost = count, cost + spent
            metrics.setdefault("newest_indexed", newest)
        except goanyapi.GoAnyError as exc:
            errors.append(f"recent pages ({window}): {exc}")
    if metrics.get("indexed_month") != 0:
        return metrics, [], cost, errors
    added = site_activity(domain, today)
    metrics["sitemap_changed_30d"] = added
    if added and added >= ACTIVE_MIN:
        return metrics, [flag("not_indexing", f"its sitemap lists {added} pages changed in {RECENT_DAYS} days; site: search "
                              f"for the same window returned none, asked twice. Google calls site: counts incomplete "
                              f"and new pages can take weeks: check again before paying")], cost, errors
    return metrics, [flag("inactive", "sitemap: " + ("none readable" if added is None else f"{added} pages changed in "
                                                        f"{RECENT_DAYS} days") + "; Google: none from the last 30 days")], cost, errors


def link_profile(domain: str, today: date, fresh: bool) -> tuple[dict, list[dict], int]:
    """DataForSEO's backlink summary for the site ($0.024 through AIsa) -> (metrics, flags, cost).

    Tested on 2026-10-14 against Ahrefs' own SPAM mark on 90 sites that link to one young site
    (33 marked). External data reproduces that mark only up to a cross-validated AUC of about 0.75,
    almost all of it from three things: how new the site is, how few sites link to it, how few
    people visit. Two mechanisms are worth naming, so they are flags here:
      badge_network  7 hits, 4 marked: each linking site gives it hundreds of links, most in footers
                     and navigation, nearly all followed. Two of the unmarked look the same.
      unproven       23 hits, 17 marked: under a year in the index, under 100 linking sites, under
                     1,000 visits a month. The unmarked hits look no better.
    """
    result, cost = paid("aisa", f"summary:{domain}", lambda: aisa.call(SUMMARY_TOOL, {
        "target": domain, "include_subdomains": True, "backlinks_status_type": "live"}), fresh)
    rd = result.get("referring_domains") or 0
    places = result.get("referring_links_semantic_locations") or {}
    seen = (result.get("first_seen") or "")[:10]
    metrics = {"referring_domains": rd,
               "links_per_domain": round((result.get("backlinks") or 0) / rd, 1) if rd else None,
               "template_link_share": round(sum(places.get(k, 0) for k in TEMPLATE_PLACES) / sum(places.values()), 2)
                                      if sum(places.values()) else None,
               "nofollow_domain_share": round((result.get("referring_domains_nofollow") or 0) / rd, 2) if rd else None,
               "indexed_since": seen}
    return metrics, profile_flags(metrics, today), cost


def profile_flags(m: dict, today: date) -> list[dict]:
    flags = []
    if (m["referring_domains"] >= BADGE_MIN_DOMAINS and (m["links_per_domain"] or 0) >= BADGE_LINKS_PER_DOMAIN
            and (m["template_link_share"] or 0) >= BADGE_TEMPLATE_SHARE
            and (m["nofollow_domain_share"] if m["nofollow_domain_share"] is not None else 1) <= BADGE_MAX_NOFOLLOW):
        flags.append(flag("badge_network", f"{m['links_per_domain']:g} links from each linking site on average, "
                          f"{round(m['template_link_share'] * 100)}% in footers, navigation or sidebars, "
                          f"{round(m['nofollow_domain_share'] * 100)}% of linking sites nofollow"))
    age = (today - date.fromisoformat(m["indexed_since"])).days if m["indexed_since"] else None
    if (age is None or age < UNPROVEN_DAYS) and m["referring_domains"] < UNPROVEN_DOMAINS:
        flags.append(flag("unproven", f"in DataForSEO's index for {age if age is not None else 'no'} days, "
                          f"{m['referring_domains']} linking sites"))
    return flags


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


def vet_one(raw: str, paid_sources: bool, today: date, known: list[dict], fresh: bool, recent: bool = False,
            deep: bool = False) -> dict:
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
        if recent:
            more, found, spent, failed = recent_flags(t["domain"], today, fresh)
            metrics.update(more)
            flags, cost, errors = flags + found, cost + spent, errors + failed
    if deep and paid_sources and aisa.key():
        try:
            more, found, spent = link_profile(t["domain"], today, fresh)
            busy = metrics.get("visits") is not None and metrics["visits"] >= NO_AUDIENCE
            metrics.update(more)
            flags, cost = flags + [f for f in found if not (f["flag"] == "unproven" and busy)], cost + spent
        except aisa.AisaError as exc:
            errors.append(f"link profile: {exc}")
    if metrics.get("visits", 0) >= NO_AUDIENCE and any(f["flag"] == "dead" for f in flags):
        # People visit it, so it is up: our request failed, the site did not.
        flags = [flag("blocked", f["evidence"]) if f["flag"] == "dead" else f for f in flags]
    return {**t, "title": read["parsed"]["title"][:120], "flags": flags, "metrics": metrics, "cost": cost, "errors": errors}


def template_of(row: dict) -> str:
    """The page title with the site's own name taken out: "drjack.world | Keyword Rankingss" and
    "quero.party | Keyword Rankingss" both become "{site} | keyword rankingss"."""
    title, name = row.get("title", "").lower(), row["domain"].lower()
    for variant in (name, name.split(".")[0]):
        title = title.replace(variant, "{site}")
    return " ".join(title.split())


def shared_templates(rows: list[dict]) -> None:
    """Flag the rows of a batch whose titles are one template: sites run by one operator."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        key = template_of(r)
        if len(key.replace("{site}", "").strip(" |-:")) >= TEMPLATE_MIN:
            groups.setdefault(key, []).append(r)
    for key, members in groups.items():
        if len(members) < 2:
            continue
        names = ", ".join(m["domain"] for m in members[:5])
        for m in members:
            m["flags"].append(flag("same_template", f"{len(members)} sites titled \"{key[:60]}\": {names}"))


def vet(targets: list[str], paid_sources: bool = True, today: date | None = None, fresh: bool = False,
        recent: bool = False, deep: bool = False) -> dict:
    """{"rows": [...], "cost": micro-USD, "errors": [...], "sources": {...}}. Rows keep the order given."""
    today = today or date.today()
    known = updates.ranking_updates() if paid_sources and (goanyapi.key() or aisa.key()) else []
    with ThreadPoolExecutor(WORKERS) as pool:
        rows = list(pool.map(lambda raw: vet_one(raw, paid_sources, today, known, fresh, recent, deep), targets))
    cost, errors = sum(r["cost"] for r in rows), [f"{r['domain']}: {e}" for r in rows for e in r["errors"]]
    scores = {}
    if paid_sources and aisa.key():
        try:
            scores, spent = spam_scores(sorted({r["domain"] for r in rows}), fresh)
            cost += spent
        except aisa.AisaError as exc:
            errors.append(f"spam score: {exc}")
        try:
            cost += history.check(rows, today, known, fresh)
        except aisa.AisaError as exc:
            errors.append(f"search history: {exc}")
    shared_templates(rows)
    for r in rows:
        score = scores.get(r["domain"])
        r["metrics"]["spam_score"] = score
        if score is not None and score >= SPAM_SCORE_HIGH:
            r["flags"].append(flag("spam_score", f"{score} of 100 (DataForSEO)"))
        r["flags"], r["grade"], r["reach"] = ranked(r["flags"]), grade(r["flags"]), reach(r["metrics"])
    return {"rows": rows, "cost": cost, "errors": errors,
            "sources": {"goanyapi": bool(paid_sources and goanyapi.key()), "aisa": bool(paid_sources and aisa.key()),
                        "free": not paid_sources}}
