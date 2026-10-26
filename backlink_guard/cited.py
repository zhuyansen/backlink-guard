"""Which sites Google's AI Overview cites for your keywords (0.8), and whether you are one of them.

For each keyword, Google's first page of results (US, English) with its AI Overview: the advanced results (Glasser or
AIsa) with load_async_ai_overview, which also waits for an overview Google loads after the page. $0.002 a keyword through
AIsa on 2026-10-20, $0.004 through Glasser on 2026-10-26; each adds $0.002 when the overview it waited for was loaded
late, and gives it back when not. The sites an
overview cites, its references and the links in its text, are the sources the answer was written from: being
mentioned on them is how a site gets into the answer. Your own organic position on the same page comes free.

A keyword whose results carry no AI Overview is said so: no overview is not the same as not being cited. Google shows
an overview when it judges one helpful, so another day, place or searcher can differ.
"""
from __future__ import annotations

from collections import defaultdict

from . import aisa, backend, find, page
from .budget import Budget, OverBudget

TOOL = "post_dataforseo_serp_google_organic_live"     # the advanced results: SERP features such as ai_overview
US, EN, DEPTH = 2840, "en", 10
MAX_USD = 0.10                  # about 25 keywords at the most a keyword can cost
CALL = {"AIsa": 4_000, "Glasser": 6_000}    # micro-USD a keyword costs at most: the page and a late-loaded overview
OVERVIEW = {"ai_overview", "knowledge_graph_ai_overview_item"}     # an overview of its own, or inside a knowledge panel
CITING = {"references", "links"}                                    # where an overview names its sources


def results(keyword: str, budget: Budget, fresh: bool) -> dict:
    """Google's first page for the keyword, with its AI Overview."""
    body = {"keyword": keyword, "location_code": US, "language_code": EN, "depth": DEPTH, "load_async_ai_overview": True}
    estimate = CALL[backend.name()]
    data, _ = budget.ask(f"aisa:serp-aio:{US}:{DEPTH}:{keyword.lower()}", estimate, lambda: backend.call(TOOL, body), fresh,
                         f"“{keyword}”")
    return data or {}


def overviews(node) -> list[dict]:
    """Every AI Overview in the results, wherever it sits."""
    if isinstance(node, dict):
        return [node] if node.get("type") in OVERVIEW else overviews(list(node.values()))
    if isinstance(node, list):
        return [o for x in node for o in overviews(x)]
    return []


def citations(node, citing: bool = False, found: dict | None = None) -> list[dict]:
    """[{"url", "site", "title"}]: what an overview cites (anything with a URL under its references or links), in
    order, each page once."""
    found = {} if found is None else found
    if isinstance(node, dict):
        url = node.get("url") or ""
        if citing and url.startswith(("http://", "https://")):
            title = " ".join(str(node.get("title") or node.get("source") or "").split())
            found.setdefault(url, {"url": url, "site": page.registrable(url), "title": title})
        for key, value in node.items():
            citations(value, citing or key in CITING, found)
    elif isinstance(node, list):
        for value in node:
            citations(value, citing, found)
    return list(found.values())


def your_rank(data: dict, own: str) -> tuple[int | None, str]:
    """(your best organic position on the page, its URL); (None, "") when you are not on it."""
    for item in data.get("items") or []:
        if item.get("type") == "organic" and page.registrable(item.get("url") or "") == own:
            return item.get("rank_group"), item["url"]
    return None, ""


def keyword_row(keyword: str, data: dict, own: str) -> dict:
    """{"keyword", "overview", "cited", "you", "rank", "your_page"} for one keyword's results."""
    found = overviews(data.get("items") or [])
    cited = list({c["url"]: c for o in found for c in citations(o)}.values())
    rank, url = your_rank(data, own)
    return {"keyword": keyword, "overview": bool(found), "cited": cited,
            "you": [c["url"] for c in cited if c["site"] == own], "rank": rank, "your_page": url}


def tally(rows: list[dict], own: str) -> list[dict]:
    """[{"site", "keywords", "citations", "urls", "you", "kind", "action"}]: every site cited, the most keywords first,
    with what kind of page it was cited for and what can honestly be done there (find.kind_of)."""
    by: dict[str, dict] = defaultdict(lambda: {"keywords": [], "citations": 0, "pages": {}})
    for r in rows:
        for c in r["cited"]:
            t = by[c["site"]]
            t["keywords"] += [] if r["keyword"] in t["keywords"] else [r["keyword"]]
            t["citations"] += 1
            t["pages"].setdefault(c["url"], c["title"])
    out = []
    for site, t in by.items():
        url, title = next(iter(t["pages"].items()))
        kind = find.kind_of(url, title)
        out.append({"site": site, "keywords": t["keywords"], "citations": t["citations"], "urls": list(t["pages"]),
                    "title": title, "you": site == own, "kind": kind, "action": find.ACTIONS[kind]})
    return sorted(out, key=lambda x: (-len(x["keywords"]), -x["citations"], x["site"]))


def cited(domain: str, keywords: list[str], max_usd: float = MAX_USD, fresh: bool = False) -> dict:
    """{"domain", "keywords": [keyword_row], "sites": tally, "cost", "max_usd", "left_out", "errors"}."""
    own, budget = page.registrable(page.host(domain)), Budget(max_usd)
    out = {"domain": own, "keywords": [], "sites": [], "cost": 0, "max_usd": max_usd, "left_out": [], "errors": []}
    for keyword in dict.fromkeys(" ".join(k.split()) for k in keywords if k.strip()):
        try:
            data = results(keyword, budget, fresh)
        except OverBudget:
            continue
        except aisa.AisaError as exc:
            out["errors"].append(f"“{keyword}”: {exc}")
            continue
        out["keywords"].append(keyword_row(keyword, data, own))
    out.update(sites=tally(out["keywords"], own), cost=budget.spent, left_out=budget.left_out)
    return out
