"""Check a link source before you submit to it.

For each target the check reads the site itself (free), then, when the keys are set,
asks GoAnyAPI for its rating, a year of visits and whether Google still lists it, and
Glasser or AIsa for the spam score of its own backlink profile. Each finding carries the
text or the numbers it came from, so a person can check it.

Cost with both keys: about $0.01 a target (GoAnyAPI) plus about $0.025 for the whole
batch (Glasser or AIsa). Without keys the page checks still run.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from statistics import mean

from . import UA, aisa, backend, blocklist, cache, checkout, find, glasser, goanyapi, history, page, seen, signals, updates
from .policy import action, flag, grade, policy_risk, ranked, risk, value

WORKERS = 4
RETRY_PAUSE = 5                 # seconds before a site or a search that gave no answer is asked once more
EXTRA_PAGES = 3                 # submit, pricing and similar pages read besides the home page
SNIPPET = 160
WORD_EDGE = 20                  # characters a quote gives up at each end so that it starts and ends on whole words
NEAR = 200                      # how close a price must be to the words that say what is sold
QUOTE_PAD = 30
PARKED_MAX_TEXT = 3000          # a real site that merely writes about parked domains is longer than this
SPAM_NEIGHBORS = 3
SPAM_SCORE_HIGH = 50             # 40 until 2026-10-16: it flagged 30 of 60 normal sites for 27 of 40 SPAM; 50: 20 for 19
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
LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
LANG = re.compile(r"<html[^>]*\blang=[\"']?([A-Za-z-]+)", re.I)
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
# Titles every site of a platform, a host or a block page shares: no operator's template.
GENERIC_TITLE = re.compile(r"just a moment|attention required|access denied|forbidden|not found|coming soon|"
                           r"under construction|just another wordpress site|welcome to nginx|index of /|default (?:web )?page",
                           re.I)
SUBPAGE = re.compile(r"submit|pricing|advertis|sponsor|write-?for-?us|guest-?post|list-your|get-listed", re.I)
QUALIFIED = {"nofollow", "sponsored", "ugc"}
# A site's own pages that already say avoid: the paid checks could only add to it, so they are not bought.
DECISIVE = {"dead", "parked", "link_farm", "shortener", "link_seller", "spam_neighbors", "listed"}
# The accounts a page reports to. Sites of one operator share them; the forms and the placeholder rule are the
# ones that grouped payment-link sellers by owner (2026-10-15). Stripe keys are left out: white-label shops share
# their platform's.
IDS = {
    "adsense": re.compile(r"\b(ca-pub-\d{10,20})\b"),
    "ua": re.compile(r"\bUA-(\d{4,10})-\d{1,4}\b"),            # the account number: one owner, any number of sites
    "ga4": re.compile(r"(?:gtag/js\?id=|config['\"]\s*,\s*['\"])(G-[A-Z0-9]{6,12})"),
    "gtm": re.compile(r"\b(GTM-[A-Z0-9]{5,9})\b"),
    "clarity": re.compile(r"[\"']clarity[\"']\s*,\s*[\"']script[\"']\s*,\s*[\"']([a-z0-9]{6,12})[\"']"),
    "pixel": re.compile(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"](\d{10,20})"),
    # Cloudflare Web Analytics, one token a site. 0.8: of 106 link-network pages among a competitor's new referring
    # domains (2026-10-20), one carried an AdSense or Google ID and 87 this beacon, one token on 14 of them.
    "cloudflare": re.compile(r"data-cf-beacon=[^>]*?token(?:&quot;|[\"'])?\s*:\s*(?:&quot;|[\"'])([0-9a-f]{32})"),
}
PLACEHOLDER_ID = re.compile(r"X{4,}|0{6,}|1234567", re.I)      # template IDs nobody filled in: G-XXXXXXXXXX
# Failed checks that could have found something against a site: an ok without them is not an ok. Row errors
# start with these names; the batch ones are asked once for every site.
KEY_CHECKS = ("rating", "traffic", "index", "link profile", "checkout", "recent pages")
BATCH_CHECKS = ("spam score", "search history")


def target(raw: str) -> dict:
    url = raw if raw.startswith(("http://", "https://")) else "https://" + raw.strip("/")
    return {"input": raw, "domain": page.site(url), "url": url}


def excerpt(text: str, start: int, end: int) -> str:
    """text[start:end] on whole words, with … where it cuts the text short. A word is only given up when a space
    comes within WORD_EDGE characters, so text written without spaces is cut where it falls."""
    start, end = max(0, start), min(len(text), end)
    if 0 < start < end and not text[start - 1].isspace():
        start = next((i + 1 for i in range(start, min(end, start + WORD_EDGE)) if text[i].isspace()), start)
    if start < end < len(text) and not text[end].isspace():
        end = next((i for i in range(end - 1, max(start, end - WORD_EDGE), -1) if text[i].isspace()), end)
    words = " ".join(text[start:end].split())
    return ("…" if text[:start].strip() else "") + words + ("…" if text[end:].strip() else "")


def snippet(text: str, at: int) -> str:
    start = max(0, at - SNIPPET // 2)
    return excerpt(text, start, start + SNIPPET)


def priced(text: str, what: re.Pattern) -> str:
    """A passage where `what` sits next to a price, "" when there is none."""
    for m in what.finditer(text):
        offset = max(0, m.start() - NEAR)
        price = PRICE.search(text[offset:m.end() + NEAR])
        if price:                       # quote from the first of the two to the second, so both are in view
            first, last = sorted((m.start(), offset + price.start()))
            return excerpt(text, first - QUOTE_PAD, last + QUOTE_PAD * 2)
    return ""


def read_site(url: str) -> dict:
    """The home page and up to EXTRA_PAGES pages where a site says what it charges. A home page that
    gives no answer at all (a timeout, a refused connection, no DNS) is asked once more before the
    site counts as dead; a 404 or 410 is an answer."""
    home, asked = page.fetch(url), 1
    if home["dead"] and not home["status"]:
        time.sleep(RETRY_PAUSE)
        home, asked = page.fetch(url), 2
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
    return {"home": home, "parsed": parsed, "texts": [parsed["text"]] + [e["text"] for e in extra], "asked": asked}


def page_flags(read: dict) -> list[dict]:
    home, parsed = read["home"], read["parsed"]
    if home["dead"]:
        return [flag("dead", (home["error"] or f"HTTP {home['status']}") + (", asked twice" if read.get("asked") == 2 else ""))]
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


def ids_of(html: str) -> list[str]:
    """The analytics and ads accounts a page reports to, as "kind:id", placeholders left out."""
    return sorted({f"{kind}:{m.group(1)}" for kind, form in IDS.items() for m in form.finditer(html or "")
                   if not PLACEHOLDER_ID.search(m.group(1))})


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
    """{"now", "earlier", "ratio", "cliff", "drop"} from {"2026-09-01": visits}. `now` is the last three
    months on average, `earlier` the best three in a row before them. `cliff` is (month, share kept) for a
    fall a later month confirms; `drop` is the same for a fall in the newest month, which nothing confirms
    yet. In September 2026 GoAnyAPI's visits fell 46% to 76% for 16 of 59 sites with 5,000 or more, while
    their US Google search traffic from AIsa mostly held (one directory: visits down two thirds, search down
    3%; 2026-10-15): one month of one estimate is not yet a fall."""
    months = sorted(monthly.items())
    series = [int(v or 0) for _, v in months]
    out = {"now": round(mean(series[-3:])) if series else 0, "earlier": 0, "ratio": None, "cliff": None, "drop": None}
    if len(series) >= 6:
        out["earlier"] = round(max(mean(series[i:i + 3]) for i in range(len(series) - 5)))
        out["ratio"] = round(out["now"] / out["earlier"], 2) if out["earlier"] else None
    for i in range(max(1, len(series) - CLIFF_WINDOW), len(series)):
        before, after = series[i - 1], series[i]
        if before >= MIN_LEVEL and after < before * CLIFF and series[-1] < before * RECOVERED:
            out["cliff" if i < len(series) - 1 else "drop"] = (months[i][0][:7], round(after / before, 2))
    return out


def traffic_flags(trend: dict, dr, known: list[dict]) -> list[dict]:
    flags = []
    fall = trend["cliff"] or trend.get("drop")
    if fall:
        month, kept = fall
        near = updates.around(month, known)
        flags.append(flag("traffic_cliff" if trend["cliff"] else "traffic_drop", f"{month}: down {round((1 - kept) * 100)}% on the month before"
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
    to AIsa ($0.01: a query with a search operator costs five times a plain one). Not to Glasser:
    it does not sell searches with operators such as site: (refused as invalid input, 2026-10-26)."""
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
    search sources returned nothing for sites with thousands of pages (skills.sh, 10-13).
    When both sources fail it is asked once more after a pause: AIsa's "Internal SE
    Server Error." cost two sites their deindexed flag in one of two
    runs (10-15). A second failure raises: a failure is never a zero."""
    try:
        count, cost = index_count(domain, fresh)
    except (goanyapi.GoAnyError, aisa.AisaError):
        time.sleep(RETRY_PAUSE)
        count, cost = index_count(domain, True)
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


def pages_listed(domain: str) -> int | None:
    """About how many pages the site's own sitemaps list: the sitemaps in robots.txt, an index followed
    one level down; past SITEMAPS child files, the average of those read stands in for the rest.
    Free, kept 7 days; None when there is no readable sitemap."""
    held = cache.get(f"sitemap:pages:{domain}")
    if held is not None:
        return held or None
    robots = page.fetch(f"https://{domain}/robots.txt")
    roots = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots["html"]) or [f"https://{domain}/sitemap.xml"]
    total = 0
    for root in roots[:3]:
        got = page.fetch(root)
        if got["dead"] or got["blocked"]:
            continue
        locs = LOC.findall(got["html"])
        if "<sitemapindex" not in got["html"]:
            total += len(locs)
            continue
        counts = [len(LOC.findall(page.fetch(u)["html"])) for u in locs[:SITEMAPS]]
        total += round(sum(counts) + (len(locs) - len(counts)) * sum(counts) / len(counts)) if counts else 0
    cache.put(f"sitemap:pages:{domain}", total)
    return total or None


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
    """The backlink summary for the site (Glasser or AIsa, $0.024) -> (metrics, flags, cost).

    Tested on 2026-10-14 against Ahrefs' own SPAM mark on 90 sites that link to one young site
    (33 marked). External data reproduces that mark only up to a cross-validated AUC of about 0.75,
    almost all of it from three things: how new the site is, how few sites link to it, how few
    people visit. Two mechanisms are worth naming, so they are flags here:
      badge_network  7 hits, 4 marked: each linking site gives it hundreds of links, most in footers
                     and navigation, nearly all followed. Two of the unmarked look the same.
      unproven       23 hits, 17 marked: under a year in the index, under 100 linking sites, under
                     1,000 visits a month. The unmarked hits look no better.
    """
    result, cost = paid("aisa", f"summary:{domain}", lambda: backend.call(SUMMARY_TOOL, {
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
        flags.append(flag("unproven", f"in {backend.name()}'s backlink index for {age if age is not None else 'no'} days, "
                          f"{m['referring_domains']} linking sites"))
    return flags


def market(domain: str, known: list[dict], fresh: bool, traffic: dict | None = None) -> tuple[dict, list[dict], int, list[str]]:
    """Rating, visits and index status. (metrics, flags, cost, errors). `traffic` is a visits answer already bought."""
    metrics, flags, cost, errors = {}, [], 0, []
    try:
        data, spent = paid("goanyapi", f"dr:{domain}", lambda: goanyapi.call("dr", domain=domain), fresh)
        metrics["dr"], cost = data.get("domain_rating"), cost + spent
    except goanyapi.GoAnyError as exc:
        errors.append(f"rating: {exc}")
    try:
        data, spent = (traffic, 0) if traffic else \
            paid("goanyapi", f"traffic:{domain}", lambda: goanyapi.call("traffic", domain=domain, month=12), fresh)
        trend = visit_trend(data.get("EstimatedMonthlyVisits") or {})
        metrics.update(visits=trend["now"], visits_vs_earlier=trend["ratio"], **signals.audience(data))
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


def visits_of(domain: str, fresh: bool) -> tuple[dict | None, int, list[str]]:
    """(the visits answer, cost, errors): the one paid question a site that does not load gets. A site found
    busy hands the same answer on to market(), so it is not bought twice."""
    try:
        data, cost = paid("goanyapi", f"traffic:{domain}", lambda: goanyapi.call("traffic", domain=domain, month=12), fresh)
    except goanyapi.GoAnyError as exc:
        return None, 0, [f"traffic: {exc}"]
    return data, cost, []


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
    result, cost = backend.call(SPAM_TOOL, {"targets": missing})
    for item in result.get("items") or []:
        scores[item["target"]] = item.get("spam_score")
        cache.put(f"aisa:spam:{item['target']}", item.get("spam_score"))
    return scores, cost


def mentions(read: dict, topics: list[str]) -> bool:
    """Whether the pages read carry every word of one of your topics."""
    text = " ".join(read["texts"]).lower()
    stem = lambda w: w[:-1] if len(w) > 3 and w.endswith("s") else w  # noqa: E731 — "skills" also finds "skill"
    return any(all(stem(w) in text for w in t.lower().split()) for t in topics)


def vet_one(raw: str, paid_sources: bool, today: date, known: list[dict], fresh: bool, recent: bool = False,
            deep: bool = False, topics: tuple[str, ...] = (), listed: dict | None = None) -> dict:
    t = target(raw)
    read = read_site(t["url"])
    flags, metrics, cost, errors = page_flags(read), outbound(read), 0, []
    flags += [f for f in [blocklist.flag_for(t["domain"], listed or {})] if f]
    metrics["ids"] = ids_of(read["home"].get("html") or "")
    if topics:
        metrics["mentions"] = mentions(read, list(topics))
    archived = first_seen(t["domain"])
    metrics["first_seen"] = archived
    if archived and (today - datetime.strptime(archived, "%Y-%m-%d").date()).days < YOUNG_DAYS:
        flags.append(flag("young", f"first archived {archived}"))
    lang = LANG.search(read["home"].get("html") or "")
    metrics["lang"] = lang.group(1).lower() if lang else None
    settled, traffic = sorted({f["flag"] for f in flags} & DECISIVE), None
    if paid_sources and settled == ["dead"] and goanyapi.key():
        traffic, cost, errors = visits_of(t["domain"], fresh)       # people visit it: blocked, not dead
        visits = visit_trend(traffic.get("EstimatedMonthlyVisits") or {})["now"] if traffic else None
        metrics.update({} if visits is None else {"visits": visits})
        settled = [] if (visits or 0) >= NO_AUDIENCE else settled
    if paid_sources and settled:
        return {**t, "title": read["parsed"]["title"][:120], "flags": flags, "metrics": metrics, "cost": cost,
                "errors": errors, "skipped": settled}
    if paid_sources and backend.key():
        metrics["pages_listed"] = pages_listed(t["domain"])   # weighed against its rankings in history.check
    if paid_sources and goanyapi.key():
        more, found, spent, failed = market(t["domain"], known, fresh, traffic)
        metrics.update(more)
        cost, errors = cost + spent, errors + failed
        flags += [f for f in [signals.reregistered(archived, metrics.get("registered"), today, metrics.get("visits"))] + found if f]
        try:
            note, spent = signals.guest_posts(t["domain"], lambda q, fn: paid("goanyapi", q, fn, fresh))
            flags, cost = flags + ([note] if note else []), cost + spent
        except goanyapi.GoAnyError as exc:
            errors.append(f"guest posts: {exc}")
    if paid_sources and backend.key():
        found, spent, failed = checkout.shared(read, page.site(t["url"]), lambda q, fn: paid("aisa", q, fn, fresh), SPAM_WORDS,
                                               deep=deep)
        flags, cost, errors = flags + found, cost + spent, errors + failed
    if paid_sources:
        metrics["entity"] = signals.entity(t["domain"])
        if recent:
            more, found, spent, failed = recent_flags(t["domain"], today, fresh)
            metrics.update(more)
            flags, cost, errors = flags + found, cost + spent, errors + failed
    if deep and paid_sources and backend.key():
        more, spent, failed = signals.deep(t["domain"], today, lambda q, fn: paid("aisa", q, fn, fresh))
        metrics.update(more)
        cost, errors = cost + spent, errors + failed
        try:
            more, found, spent = link_profile(t["domain"], today, fresh)
            metrics.update(more)
            flags, cost = flags + found, cost + spent
        except aisa.AisaError as exc:
            errors.append(f"link profile: {exc}")
    return {**t, "title": read["parsed"]["title"][:120], "flags": flags, "metrics": metrics, "cost": cost, "errors": errors}


def template_of(row: dict) -> str:
    """The page title with the site's own name taken out: "drjack.world | Keyword Rankingss" and
    "quero.party | Keyword Rankingss" both become "{site} | keyword rankingss"."""
    title, name = row.get("title", "").lower(), row["domain"].lower()
    for variant in (name, name.split(".")[0]):
        title = title.replace(variant, "{site}")
    return " ".join(title.split())


def templates(rows: list[dict]) -> dict[str, list[str]]:
    """{template: [sites]} for the titles long and particular enough to say something."""
    groups: dict[str, list[str]] = {}
    for r in rows:
        key = template_of(r)
        if len(key.replace("{site}", "").strip(" |-:")) >= TEMPLATE_MIN and not GENERIC_TITLE.search(key):
            groups.setdefault(key, []).append(r["domain"])
    return groups


def accounts(rows: list[dict]) -> dict[str, list[str]]:
    """{analytics or ads account: [sites]}."""
    owners: dict[str, list[str]] = {}
    for r in rows:
        for account in r["metrics"].get("ids") or []:
            owners.setdefault(account, []).append(r["domain"])
    return owners


def since(earlier: list[str]) -> str:
    return f"; {len(earlier)} of them from earlier checks" if earlier else ""


def shared_templates(rows: list[dict], before: dict[str, dict[str, str]] | None = None) -> list[dict]:
    """Flag the rows whose titles are one template, counting the sites seen with it in earlier checks (`before`,
    {template: {site: date}}): sites run by one operator. Returns the groups."""
    by_site, found = {r["domain"]: r for r in rows}, []
    for key, here in templates(rows).items():
        earlier = sorted(d for d in (before or {}).get(key, {}) if d not in by_site)
        if len(here) + len(earlier) < 2:
            continue
        sites = here + earlier
        for d in here:
            by_site[d]["flags"].append(flag("same_template", f"{len(sites)} sites titled \"{key[:60]}\": "
                                                             f"{', '.join(sites[:5])}{since(earlier)}"))
        found.append({"kind": "template", "key": key, "sites": sites})
    return found


def shared_owners(rows: list[dict], before: dict[str, dict[str, str]] | None = None) -> list[dict]:
    """Flag the rows that report to one analytics or ads account, counting the sites seen with it in earlier
    checks: one operator's sites. Returns the groups."""
    here = {r["domain"] for r in rows}
    owners = {a: sorted(set(sites)) + sorted(set((before or {}).get(a, {})) - here) for a, sites in accounts(rows).items()}
    for r in rows:
        mine = sorted(a for a in r["metrics"].get("ids") or [] if len(owners[a]) >= 2)
        if mine:
            others = sorted(set().union(*(owners[a] for a in mine)) - {r["domain"]})
            more = f" and {len(others) - 4} more" if len(others) > 4 else ""
            earlier = [d for d in others if d not in here]
            r["flags"].append(flag("same_owner", f"{', '.join(mine[:2])} also on {', '.join(others[:4])}{more}{since(earlier)}"))
    return [{"kind": "owner", "key": a, "sites": sites} for a, sites in owners.items() if len(sites) >= 2]


def missing(r: dict, batch_failed: tuple[str, ...] = ()) -> list[str]:
    """The checks that could have found something against the site and failed."""
    return [k for k in KEY_CHECKS if any(e.startswith(k) for e in r.get("errors", []))] + \
        [b for b in BATCH_CHECKS if b in batch_failed]


def finalize(r: dict, batch_failed: tuple[str, ...] = ()) -> dict:
    """The verdict from what was found: findings weighed against the site's numbers, then grade, reach and risk.
    It reads only the row, so a saved row can be graded again when a rule changes (scripts/regress.py)."""
    m, visits = r["metrics"], r["metrics"].get("visits") or 0
    flags = [f for f in r["flags"] if f["flag"] != "spam_score"]
    if visits >= NO_AUDIENCE:           # people visit it: a failed request was ours, and it is not unproven
        flags = [flag("blocked", f["evidence"]) if f["flag"] == "dead" else f for f in flags if f["flag"] != "unproven"]
    if visits >= REACH_HIGH:            # github.com and pypi.org have the badge profile: every project links them
        flags = [f for f in flags if f["flag"] != "badge_network"]
    if (m.get("spam_score") or 0) >= SPAM_SCORE_HIGH:
        flags.append(flag("spam_score", f"{m['spam_score']} of 100 ({m.get('spam_by') or 'AIsa'})"))
    r["flags"], r["reach"], r["missing"] = ranked(flags), reach(m), missing(r, batch_failed)
    r["grade"], r["risk"] = grade(r["flags"]), risk(r["flags"])
    r["policy"], r["value"] = policy_risk(r["flags"]), value(r["flags"], r["reach"])
    if r["grade"] == "ok" and r["missing"]:
        r["grade"] = "incomplete"       # an ok it could not finish checking is not an ok
    r["action"], r["action_reason"] = action(r)
    return r


def vet(targets: list[str], paid_sources: bool = True, today: date | None = None, fresh: bool = False,
        recent: bool = False, deep: bool = False, topics: tuple[str, ...] = (), referrals: dict[str, int] | None = None) -> dict:
    """{"rows": [...], "cost": micro-USD, "errors": [...], "sources": {...}}. Rows keep the order given.
    `referrals` ({site: visits} from your own analytics) adds what each site has sent you: a reach no estimate gives."""
    today = today or date.today()
    known = updates.ranking_updates() if paid_sources and (goanyapi.key() or backend.key()) else []
    try:
        listed, unread = blocklist.load(fresh), []
    except (OSError, ValueError) as exc:
        listed, unread = {}, [f"spam list: {exc}"]
    with ThreadPoolExecutor(WORKERS) as pool:
        rows = list(pool.map(lambda raw: vet_one(raw, paid_sources, today, known, fresh, recent, deep, topics, listed), targets))
    cost, errors = sum(r["cost"] for r in rows), unread + [f"{r['domain']}: {e}" for r in rows for e in r["errors"]]
    live, scores, failed = [r for r in rows if not r.get("skipped")], {}, []
    if paid_sources and backend.key() and live:
        try:
            scores, spent = spam_scores(sorted({r["domain"] for r in live}), fresh)
            cost += spent
        except aisa.AisaError as exc:
            errors.append(f"spam score: {exc}")
            failed.append("spam score")
        try:
            cost += history.check(live, today, known, fresh)
        except aisa.AisaError as exc:
            errors.append(f"search history: {exc}")
            failed.append("search history")
        if topics:
            try:
                cost += find.fit(live, list(topics), fresh)
            except aisa.AisaError as exc:
                errors.append(f"fit: {exc}")
    store = seen.load()
    groups = shared_templates(rows, store["templates"]) + shared_owners(rows, store["ids"])
    for r in rows:
        r["metrics"]["spam_score"] = scores.get(r["domain"])
        if r["metrics"]["spam_score"] is not None:
            r["metrics"]["spam_by"] = backend.name()      # named in its finding; a saved row keeps who said it
        if referrals is not None:
            r["metrics"]["sent_you"] = referrals.get(r["domain"], 0)
        finalize(r, () if r.get("skipped") else tuple(failed))
    errors += remember(rows, store, today)
    return {"rows": rows, "cost": cost, "errors": errors, "networks": blocklist.unlisted(groups, rows, None if unread else listed, today),
            "sources": {"goanyapi": bool(paid_sources and goanyapi.key()), "glasser": bool(paid_sources and glasser.key()),
                        "aisa": bool(paid_sources and aisa.key()), "deep": bool(paid_sources and deep), "free": not paid_sources}}


def remember(rows: list[dict], store: dict, today: date) -> list[str]:
    """Keep this run's page templates and accounts for the next checks; an error when they cannot be written."""
    seen.record(store, "templates", templates(rows), today)
    seen.record(store, "ids", accounts(rows), today)
    try:
        seen.save(store)
    except OSError as exc:
        return [f"memory of networks: {exc}"]
    return []
