"""Does a link source still take new sites? Read off its own newest pages, free (0.11).

A directory that only lists established sites will not take a new one, whatever its submit page says. Its sitemaps
name its pages with the day each last changed. The NEWEST of them, its latest listings as a rule, are read for the
sites they link to from their body (not the header, navigation, sidebar, footer or comments), and each site's
registration day is asked of RDAP, the registries' public record (rdap.org), one request every RDAP_GAP seconds: a
burst is refused. When a registry keeps no RDAP record (.io, .me and .so had none on 2026-10-27), the Wayback Machine's
first copy stands in; when RDAP does not answer, twice, the site stays undated: a first copy can be years after the
registration (a site registered in 2025 was first archived in September 2026). The share of the dated sites registered
within YOUNG_DAYS before the page changed is the answer.

Unknown, and said why, when the sitemaps carry no dates, the pages cannot be read, or their links go through the
site's own redirects (/go/123): those are not followed, since following one counts as a visit the source may report to
the site it lists. Sites that FURNITURE_SHARE or more of the pages link to, once FURNITURE_PAGES or more are read (its
social accounts, sponsors, its owner's other sites), are its furniture, not listings, and are left out, as are the
subdomains of hosting platforms (page.HOSTED), whose registration says nothing about the site on them.
"""
from __future__ import annotations

import http.client
import json
import re
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from . import UA, cache, page
from .vet import SITEMAPS, WAYBACK_TIMEOUT, first_seen as first_copy

NEWEST = 8              # newest sitemap pages read
SITES_MAX = 20          # linked sites dated at most
YOUNG_DAYS = 183        # registered this soon before the page changed: a new site
FURNITURE_SHARE = 0.8     # a site linked from nearly every page read is the source's own furniture ...
FURNITURE_PAGES = 3       # ... once this many pages are read
LISTING_PLACES = {"body text", "main area", "unknown"}
RDAP = "https://rdap.org/domain/"
RDAP_TTL_DAYS = 30      # a registration day does not change
RDAP_GAP = 0.5          # seconds between RDAP requests
RETRY_PAUSE = 5         # seconds before an RDAP request that got no answer is sent once more
WORKERS = 4
URL_BLOCK = re.compile(r"<url>(.*?)</url>", re.S)
LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
LASTMOD = re.compile(r"<lastmod>\s*(\d{4}-\d{2}-\d{2})")


def dated(xml: str) -> list[tuple[str, str]]:
    """[(url, day)]: the pages of one sitemap that carry a last-changed day."""
    out = []
    for block in URL_BLOCK.findall(xml):
        loc, mod = LOC.search(block), LASTMOD.search(block)
        if loc and mod:
            out.append((loc.group(1), mod.group(1)))
    return out


def sitemap_pages(domain: str) -> tuple[list[tuple[str, str]], int]:
    """(the dated pages of the site's sitemaps, robots.txt's or /sitemap.xml, an index followed one level down,
    SITEMAPS files at most; how many files answered)."""
    robots = page.fetch(f"https://{domain}/robots.txt")
    maps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots["html"]) or [f"https://{domain}/sitemap.xml"]
    found, read, answered = [], 0, 0
    while maps and read < SITEMAPS:
        got = page.fetch(maps.pop(0))
        read += 1
        if got["dead"] or got["blocked"] or not got["html"]:
            continue
        answered += 1
        if "<sitemapindex" in got["html"]:
            maps += LOC.findall(got["html"])[:SITEMAPS]
        found += dated(got["html"])
    return found, answered


def newest(pages: list[tuple[str, str]], domain: str, n: int = NEWEST) -> list[tuple[str, str]]:
    """The n pages changed last, the home page left out, each once."""
    home = {f"https://{domain}", f"https://www.{domain}", f"http://{domain}", f"http://www.{domain}"}
    seen, out = set(), []
    for url, mod in sorted(pages, key=lambda p: p[1], reverse=True):
        if url.rstrip("/") in home or url in seen:
            continue
        seen.add(url)
        out.append((url, mod))
    return out[:n]


def listed_sites(html: str, url: str) -> set[str]:
    """The sites a page links to from its body, hosting platforms left out."""
    links = page.external(page.parse(html, url)["links"], url)
    sites = {page.registrable(l["href"]) for l in links if l.get("placement", "unknown") in LISTING_PLACES}
    return {s for s in sites if s and not any(s.endswith("." + h) for h in page.HOSTED)}


_spacing = threading.Lock()
_last = [0.0]


def _ask_rdap(domain: str) -> tuple[str, str]:
    """(day, "ok"); ("", "none") when the registry keeps no record of it; ("", "failed") when no answer came."""
    req = urllib.request.Request(RDAP + domain, headers={"User-Agent": UA, "Accept": "application/rdap+json"})
    for attempt in range(2):
        with _spacing:                       # held while waiting: the requests leave one at a time
            time.sleep(max(0.0, _last[0] + RDAP_GAP - time.monotonic()))
            _last[0] = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=WAYBACK_TIMEOUT) as res:
                events = json.load(res).get("events") or []
            day = next(((e.get("eventDate") or "")[:10] for e in events if e.get("eventAction") == "registration"), "")
            return (day, "ok") if day else ("", "none")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return "", "none"
        except (OSError, ValueError, http.client.HTTPException):
            pass
        if not attempt:
            time.sleep(RETRY_PAUSE)
    return "", "failed"


def registered(domain: str) -> tuple[str, str]:
    """_ask_rdap's answer, kept RDAP_TTL_DAYS; a failure is not kept."""
    held = cache.get(f"rdap:{domain}", RDAP_TTL_DAYS)
    if held is not None:
        return tuple(held)
    got = _ask_rdap(domain)
    if got[1] != "failed":
        cache.put(f"rdap:{domain}", list(got))
    return got


def born(domain: str) -> tuple[str, str]:
    """(day, "registered" | "first archived" | ""): RDAP's registration day; the first archived copy when the
    registry keeps no RDAP record; nothing when RDAP did not answer."""
    day, status = registered(domain)
    if day:
        return day, "registered"
    archived = first_copy(domain) if status == "none" else ""
    return (archived, "first archived") if archived else ("", "")


def takes_new(domain: str, today: date | None = None) -> dict:
    """{"pages", "sites", "dated", "young", "share", "newest", "examples": [{"site", "day", "from", "age_days"}],
    "unknown": why or ""}. share: the dated sites registered within YOUNG_DAYS before the page that links them."""
    out = {"pages": 0, "sites": 0, "dated": 0, "young": 0, "share": None, "newest": "", "examples": [], "unknown": ""}
    pages, answered = sitemap_pages(page.site(domain))
    picked = newest(pages, page.site(domain))
    if not picked:
        out["unknown"] = "its sitemaps carry no dates" if answered else "no readable sitemap"
        return out
    out["newest"] = picked[0][1]
    with ThreadPoolExecutor(WORKERS) as pool:
        got = list(pool.map(lambda p: page.fetch(p[0]), picked))
    per_page = [(listed_sites(g["html"], g["final"] or url), mod) for g, (url, mod) in zip(got, picked) if g["html"]]
    out["pages"] = len(per_page)
    return _dated(out, per_page, page.site(domain))


def _dated(out: dict, per_page: list[tuple[set[str], str]], own: str) -> dict:
    """The linked sites of the pages read, furniture left out, each dated against the newest page linking it."""
    if not per_page:
        out["unknown"] = "its newest pages could not be read"
        return out
    used = Counter(s for sites, _ in per_page for s in sites)
    furniture = {s for s, n in used.items() if len(per_page) >= FURNITURE_PAGES and n / len(per_page) >= FURNITURE_SHARE}
    when: dict[str, str] = {}
    for sites, mod in per_page:
        for s in sites - furniture - {own}:
            when[s] = max(when.get(s, ""), mod)
    out["sites"] = len(when)
    if not when:
        out["unknown"] = "its newest pages link to no other site from their body (redirects or scripts)"
        return out
    picked = sorted(when, key=lambda s: when[s], reverse=True)[:SITES_MAX]
    with ThreadPoolExecutor(WORKERS) as pool:
        births = dict(zip(picked, pool.map(born, picked)))
    rows = [{"site": s, "day": d, "from": f, "age_days": (date.fromisoformat(when[s]) - date.fromisoformat(d)).days}
            for s, (d, f) in births.items() if d]
    young = [r for r in rows if 0 <= r["age_days"] <= YOUNG_DAYS]
    out.update(dated=len(rows), young=len(young), share=round(len(young) / len(rows), 2) if rows else None,
               examples=sorted(young, key=lambda r: r["age_days"])[:5])
    if not rows:
        out["unknown"] = "none of the sites it links to could be dated"
    return out
