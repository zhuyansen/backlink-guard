"""The backlinks to your own site, one row a link, grouped by the site they come from.

A count of links says little on its own: one site that puts your link in its footer gives you as many
links as it has pages. So every count here comes with the number of referring domains (the registrable
domain, page.registrable), and a site that links to one page of yours from many of its own pages is a
site-wide source: counted once wherever a share or a ratio is worked out, and said so.

The rows come from AIsa's backlink list (DataForSEO, up to ROWS links, strongest linking pages first:
$0.028 for 100 rows on 2026-10-18, so about $0.06 for 1,000), or, without an AIsa key, from the top
linking pages GoAnyAPI returns with your backlink summary (about 20 rows, already paid for by `audit`).
"""
from __future__ import annotations

import urllib.parse
from collections import Counter, defaultdict

from . import aisa, goanyapi, page
from .policy import flag
from .vet import TEMPLATE_PLACES, paid

TOOL = "post_dataforseo_backlinks_backlinks_live"
ROWS = 1000                 # links asked for; DataForSEO's most in one call
SITEWIDE_PAGES = 20         # pages of one site linking to one page of yours: a site-wide link
TEMPLATE_PAGES = 3          # ... or this many, most of them in a footer, sidebar, header or navigation
TEMPLATE_SHARE = 0.5


def clean(url: str) -> str:
    """The URL without its fragment, with a path: "https://a.example" and "https://a.example/#top" are one page."""
    parts = urllib.parse.urlsplit(url.strip())
    return urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))


def row(url_from: str, url_to: str, anchor: str, rank, place: str = "", followed: bool | None = None) -> dict:
    return {"from": url_from, "site": page.registrable(url_from), "to": clean(url_to) if url_to else "",
            "anchor": " ".join((anchor or "").split()), "rank": rank, "place": (place or "").lower(), "followed": followed}


def from_aisa(domain: str, fresh: bool, limit: int = ROWS) -> tuple[list[dict], int, int]:
    """(rows, how many backlinks AIsa knows in all, cost)."""
    data, cost = paid("aisa", f"backlinks:{domain}:{limit}", lambda: aisa.call(TOOL, {
        "target": domain, "mode": "as_is", "limit": limit, "backlinks_status_type": "live", "include_subdomains": True}), fresh)
    rows = [row(i.get("url_from") or "", i.get("url_to") or "", i.get("anchor") or "", i.get("domain_from_rank"),
                i.get("semantic_location") or "", i.get("dofollow")) for i in (data or {}).get("items") or []]
    return [r for r in rows if r["site"]], int((data or {}).get("total_count") or len(rows)), cost


def from_goanyapi(top: list[dict]) -> list[dict]:
    """The top linking pages of `audit` (GoAnyAPI's summary) as rows: no placement, rating for strength."""
    return [row(t["from"], t.get("to") or "", t.get("anchor") or "", t.get("dr")) for t in top if t.get("from")]


def fetch(domain: str, fresh: bool, limit: int = ROWS, top: list[dict] | None = None) -> dict:
    """{"rows", "total", "source", "strength", "cost", "errors"}: AIsa when there is a key, else GoAnyAPI's top
    linking pages (`top`, or asked for here)."""
    out = {"rows": [], "total": 0, "source": "", "strength": "", "cost": 0, "errors": []}
    if aisa.key():
        try:
            out["rows"], out["total"], out["cost"] = from_aisa(domain, fresh, limit)
            out.update(source="AIsa", strength="AIsa rank")
            return out
        except aisa.AisaError as exc:
            out["errors"].append(f"backlinks: {exc}")
    if top is None and goanyapi.key():
        from .profile import summary        # profile imports this module
        try:
            _, top, out["cost"] = summary(domain, fresh)
        except goanyapi.GoAnyError as exc:
            out["errors"].append(f"links: {exc}")
    if not aisa.key() and not goanyapi.key() and top is None:
        out["errors"].append("backlinks: no AISA_API_KEY or GOANYAPI_API_KEY, so no backlinks were read")
    if top:
        out["rows"] = from_goanyapi(top)
        out.update(total=len(out["rows"]), source="GoAnyAPI's top linking pages", strength="rating")
    return out


def sitewide(rows: list[dict], pages_min: int = SITEWIDE_PAGES) -> list[dict]:
    """The site-wide sources: one referring domain linking to one page of yours from `pages_min` or more of its
    pages, or from TEMPLATE_PAGES or more with most of the links in its template (footer, sidebar, header,
    navigation). [{"site", "to", "links", "pages", "template", "anchor"}], most pages first."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["site"], r["to"])].append(r)
    found = []
    for (site, to), links in groups.items():
        pages = len({r["from"] for r in links})
        template = sum(1 for r in links if r["place"] in TEMPLATE_PLACES) / len(links)
        if pages >= pages_min or (pages >= TEMPLATE_PAGES and template >= TEMPLATE_SHARE):
            anchor = Counter(r["anchor"] for r in links).most_common(1)[0][0]
            found.append({"site": site, "to": to, "links": len(links), "pages": pages, "template": round(template, 2),
                          "anchor": anchor})
    return sorted(found, key=lambda g: (-g["pages"], g["site"]))


def counted(rows: list[dict], groups: list[dict]) -> list[dict]:
    """The rows with each site-wide source kept as one link (its first row, with its most common anchor)."""
    wide = {(g["site"], g["to"]): g for g in groups}
    kept, seen = [], set()
    for r in rows:
        key = (r["site"], r["to"])
        if key not in wide:
            kept.append(r)
        elif key not in seen:
            seen.add(key)
            kept.append({**r, "anchor": wide[key]["anchor"]})
    return kept


def anchors(rows: list[dict], groups: list[dict]) -> list[tuple[str, int, int]]:
    """[(anchor, links, referring domains)], most links first, a site-wide source counted once."""
    links, domains = Counter(), defaultdict(set)
    for r in counted(rows, groups):
        links[r["anchor"]] += 1
        domains[r["anchor"]].add(r["site"])
    return [(a, n, len(domains[a])) for a, n in links.most_common()]


def collapse(table: list[tuple], groups: list[dict], rows: list[dict]) -> list[tuple]:
    """An anchor table counted elsewhere (AIsa's anchors, with --deep) with the site-wide sources counted once:
    each source's links come off its anchors, and one link goes back on its most common anchor."""
    off = Counter()
    wide = {(g["site"], g["to"]): g for g in groups}
    for r in rows:
        if (r["site"], r["to"]) in wide:
            off[r["anchor"]] += 1
    for g in groups:
        off[g["anchor"]] -= 1
    out = [(a, max(n - off.get(a, 0), 0), *rest) for a, n, *rest in table]
    return sorted((t for t in out if t[1]), key=lambda t: -t[1])


def domains(rows: list[dict]) -> int:
    return len({r["site"] for r in rows})


def sitewide_flag(groups: list[dict]) -> dict | None:
    """A note naming the site-wide sources, and that each is counted once."""
    if not groups:
        return None
    parts = [f"{g['links']} links from {g['pages']} pages of {g['site']} to {urllib.parse.urlsplit(g['to']).path or '/'}"
             + (f", {round(g['template'] * 100)}% in its footer, sidebar or navigation" if g["template"] else "")
             for g in groups[:4]]
    more = f"; and {len(groups) - 4} more" if len(groups) > 4 else ""
    return flag("sitewide", "; ".join(parts) + more + ". Each site counted once in the shares here")


def counted_once(groups: list[dict]) -> str:
    """"312 links from 1 site, counted once" for the totals line; "" when there are none."""
    if not groups:
        return ""
    links, sites = sum(g["links"] for g in groups), len({g["site"] for g in groups})
    return f"{links:,} links from {sites} site{'s' if sites > 1 else ''}, counted once"
