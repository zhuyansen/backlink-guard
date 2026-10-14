"""Where the people searching your keywords land, when it is not you: the pages worth being on.

A link is first of all a way in for visitors. A page that ranks for your keyword already
gets the people looking for what you make, so a mention there sends them on: the most
precise referral traffic there is, and relevant by construction. For each keyword this
reads Google's top 30 (DataForSEO through AIsa, $0.005 a keyword) and the keyword's
monthly searches ($0.012 a call), sorts the pages by the visitors they get from these
searches, and says what kind of page each is and what can honestly be done there.

The estimate is searches times the share of clicks a position usually gets; it is a
size, not a count. Nothing here is a link to buy: a paid placement must carry
rel="sponsored" or nofollow.
"""
from __future__ import annotations

import re

from . import aisa, cache
from .page import host, site

SERP_TOOL = "post_dataforseo_serp_google_organic_live_regular"
VOLUME_TOOL = "post_dataforseo_labs_google_keyword_overview_live"
US, EN, DEPTH = 2840, "en", 30
# Share of a search's clicks by position (first page), as in the keyword table's traffic estimate.
CTR = {1: .276, 2: .158, 3: .11, 4: .084, 5: .063, 6: .049, 7: .039, 8: .033, 9: .027, 10: .024}
CTR_PAGE_TWO, CTR_PAGE_THREE = .01, .003

VIDEO = {"youtube.com", "youtu.be", "vimeo.com", "tiktok.com", "bilibili.com"}
COMMUNITY = {"reddit.com", "ycombinator.com", "quora.com", "stackoverflow.com", "stackexchange.com", "x.com",
             "twitter.com", "linkedin.com", "facebook.com", "discord.com", "indiehackers.com"}
# Sites where anyone publishes: the page and its author matter, the platform's numbers do not.
PLATFORMS = {"github.com", "medium.com", "dev.to", "substack.com", "hashnode.dev", "wordpress.com", "blogspot.com",
             "notion.site", "plainenglish.io", "hackernoon.com", "gitbook.io", *VIDEO, *COMMUNITY}
DOCS_HOST = re.compile(r"^(docs|support|help|academy|learn|developers?|platform)\.")
DOCS_PATH = re.compile(r"/(docs|help|support|documentation)(/|$)")
LISTICLE = re.compile(r"\b(?:best|top)\b|\b\d+\s+(?:must-have|essential|great|free)\b|^\W*(?:the\s+)?\d+\s|"
                      r"\b\d+\s+(?:[\w-]+\s+){0,3}(?:tools|skills|apps|plugins|servers|agents|extensions|sites|examples)\b|"
                      r"\b(?:tried|tested|reviewed|compared)\s+\d+|\balternatives?\b|\bvs\.?\s|\bcompar|\bawesome\b|\blist of\b",
                      re.I)
LIST_PATH = re.compile(r"(?:^|/|-)(?:best|top-\d+|alternatives?|vs)(?:-|/|$)")
DIRECTORY = re.compile(r"\b(?:directory|library|marketplace|market|hub|catalog(?:ue)?|collection|registry|gallery)\b", re.I)
DIRECTORY_PATH = re.compile(r"/(category|categories|tag|tags|collections?|directory|browse)(/|$)|"
                            r"^/(tools?|skills?|agents?|apps?|plugins?|servers?|mcp|products?|startups?)(/[^/]+)?/?$")
GITHUB_TOPIC = re.compile(r"^/topics/([^/?#]+)")

ACTIONS = {
    "list": "Ask to be added: a pull request to a GitHub list, a short note to the author of an article list",
    "directory": "Submit, after `vet` says it is worth it",
    "article": "Offer the author what the page lacks (data, a working example); a mention reaches its readers",
    "video": "A creator who covered this: a review or a sponsored mention, marked as such",
    "community": "Answer where it helps; links there are nofollow or ugc, the visitors are the value",
    "repo": "A project people use for this: an integration or a pull request, not a link request",
    "docs": "Official documentation: not a link source",
    "site": "A product's or a site's home page: likely a competitor, not a source",
}
ORDER = ["list", "directory", "article", "video", "community", "repo", "site", "docs"]


def ctr(position: int) -> float:
    return CTR.get(position, CTR_PAGE_TWO if position <= 20 else CTR_PAGE_THREE)


def kind_of(url: str, title: str) -> str:
    """What sort of page a result is, from its address and title."""
    h, s = host(url), site(url)
    path = re.sub(r"^https?://[^/]+", "", url).split("?")[0]
    if s in VIDEO:
        return "video"
    if s in COMMUNITY:
        return "community"
    if s == "github.com":
        if GITHUB_TOPIC.match(path):
            return "directory"
        return "list" if re.search(r"awesome", path + " " + title, re.I) else "repo"
    if DOCS_HOST.match(h) or DOCS_PATH.search(path):
        return "docs"
    if path.strip("/") == "":                     # a home page: a directory's, or a product's own
        return "directory" if DIRECTORY.search(title) else "site"
    if LIST_PATH.search(path):
        return "list"
    if DIRECTORY_PATH.search(path):              # a directory's category or item page
        return "directory"
    if LISTICLE.search(title):
        return "list"
    return "directory" if DIRECTORY.search(title) else "article"


def serp(keyword: str, fresh: bool, depth: int = DEPTH) -> tuple[list[dict], int]:
    """Google's organic results for a keyword (US, English): [{"url", "title", "position"}], and the cost."""
    key = f"aisa:serp:{US}:{depth}:{keyword.lower()}"
    held = None if fresh else cache.get(key)
    if held is not None:
        return held, 0
    result, cost = aisa.call(SERP_TOOL, {"keyword": keyword, "location_code": US, "language_code": EN, "depth": depth})
    rows = [{"url": i["url"], "title": i.get("title") or "", "position": i.get("rank_absolute") or i.get("rank_group")}
            for i in result.get("items") or [] if i.get("type") == "organic" and i.get("url")]
    cache.put(key, rows)
    return rows, cost


def volumes(keywords: list[str], fresh: bool) -> tuple[dict[str, dict], int]:
    """{keyword: {"volume", "kd"}} for the keywords the cache lacks, in one call."""
    out = {} if fresh else {k: cache.get(f"aisa:volume:{US}:{k.lower()}") for k in keywords}
    out = {k: v for k, v in out.items() if v is not None}
    missing = [k for k in keywords if k not in out]
    if not missing:
        return out, 0
    result, cost = aisa.call(VOLUME_TOOL, {"keywords": missing, "location_code": US, "language_code": EN})
    for item in result.get("items") or []:
        info, props = item.get("keyword_info") or {}, item.get("keyword_properties") or {}
        out[item["keyword"]] = {"volume": info.get("search_volume") or 0, "kd": props.get("keyword_difficulty")}
    for k in missing:
        out.setdefault(k, {"volume": 0, "kd": None})
        cache.put(f"aisa:volume:{US}:{k.lower()}", out[k])
    return out, cost


def find(keywords: list[str], own: str = "", skip: tuple[str, ...] = (), fresh: bool = False) -> dict:
    """{"keywords": {kw: {"volume", "kd"}}, "pages": [...], "cost", "errors"}, pages sorted by visitors."""
    leave_out = {site(x) for x in (own, *skip) if x}
    pages: dict[str, dict] = {}
    cost, errors = 0, []
    sizes, spent = volumes(keywords, fresh)
    cost += spent
    for kw in keywords:
        try:
            rows, spent = serp(kw, fresh)
        except aisa.AisaError as exc:
            errors.append(f"{kw}: {exc}")
            continue
        cost += spent
        for r in rows:
            if site(r["url"]) in leave_out:
                continue
            p = pages.setdefault(r["url"], {"url": r["url"], "domain": site(r["url"]), "title": r["title"][:110],
                                            "kind": kind_of(r["url"], r["title"]), "ranks": [], "visitors": 0})
            p["ranks"].append({"keyword": kw, "position": r["position"]})
            p["visitors"] += round(sizes.get(kw, {}).get("volume", 0) * ctr(r["position"]))
    for p in pages.values():
        p["action"], p["platform"] = ACTIONS[p["kind"]], p["domain"] in PLATFORMS
        topic = GITHUB_TOPIC.match(re.sub(r"^https?://[^/]+", "", p["url"])) if p["domain"] == "github.com" else None
        if topic:
            p["action"] = f"Add the `{topic.group(1)}` topic to your repository: GitHub lists it on this page"
    ordered = sorted(pages.values(), key=lambda p: (ORDER.index(p["kind"]) >= ORDER.index("site"), -p["visitors"],
                                                     min(x["position"] for x in p["ranks"])))
    return {"keywords": sizes, "pages": ordered, "cost": cost, "errors": errors}


def to_vet(result: dict, limit: int) -> list[str]:
    """The sites worth vetting: directories and lists or articles on a site of their own, busiest first."""
    picked = [p["domain"] for p in result["pages"]
              if p["kind"] in ("directory", "list", "article") and not p["platform"]]
    return list(dict.fromkeys(picked))[:limit]


def fit(rows: list[dict], topics: list[str], fresh: bool) -> int:
    """Adds to each vetted row where its site ranks for your topics ("fit"); returns the cost."""
    cost, best = 0, {}
    for kw in topics:
        results, spent = serp(kw, fresh)
        cost += spent
        for r in results:
            d = site(r["url"])
            if d not in best or r["position"] < best[d]["position"]:
                best[d] = {"keyword": kw, "position": r["position"], "url": r["url"]}
    for row in rows:
        row["metrics"]["fit"] = best.get(row["domain"])
    return cost
