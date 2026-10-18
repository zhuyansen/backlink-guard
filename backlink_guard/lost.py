"""Links to pages of yours that are gone, and where each could be sent.

From the backlinks to your site (links.fetch, the same rows `audit` reads, so running both pays once),
each page of yours that gets links is asked for once, politely: a GET with the tool's own user agent,
redirects followed, a 20-second timeout, four at a time, at most CHECKED pages, the most linked first.
Only 404 and 410 make a page dead. Any other HTTP error means the request was refused (blocked), and no
answer at all means the site did not answer (unreachable): neither is called dead (page.GONE).

For each dead page the closest live page in your own sitemaps is suggested as the place to send it,
with how close the paths are (0 to 1); below MATCH_MIN there is no good match and nothing is suggested.
Nothing is redirected: it is a list for a person to read. Google's page on redirects says a page that
has moved for good takes a permanent server-side redirect (301 or 308), policy.REDIRECTS_URL.
"""
from __future__ import annotations

import re
import urllib.parse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

from . import links, page
from .policy import flag, ranked
from .vet import LOC

WORKERS = 4                 # pages of yours asked for at once
CHECKED = 200               # pages of yours asked for at most, the most referring domains first
SITEMAP_FILES = 10          # sitemap files read at most, indexes included
SITEMAP_URLS = 50_000       # URLs kept from them at most (one sitemap file's own limit)
MATCH_MIN = 0.5             # how close a path must be to be suggested
TRIES = 3                   # suggestions checked, best first, until one is live
SHORTLIST = 50              # candidates scored in full after the quick token score
EXTENSIONS = {"html", "htm", "php", "asp", "aspx", "jsp"}
SITEMAP_LINE = re.compile(r"(?im)^\s*sitemap:\s*(\S+)")


def same_page(url: str) -> str:
    """http and https, with or without www: one page of yours."""
    return links.clean(url).split("://", 1)[-1].removeprefix("www.")


def targets(rows: list[dict], domain: str) -> list[dict]:
    """The pages of yours that get links: [{"url", "domains", "links", "strongest", "rank", "sites"}], most
    referring domains first. Only links to your own site (its subdomains included) count; "url" is the
    first spelling seen of the page (same_page)."""
    own = page.registrable(domain)
    found: dict[str, dict] = defaultdict(lambda: {"url": "", "domains": set(), "links": 0, "strongest": "", "rank": None})
    for r in rows:
        if not r["to"] or page.registrable(r["to"]) != own:
            continue
        t = found[same_page(r["to"])]
        t["url"] = t["url"] or r["to"]
        t["domains"].add(r["site"])
        t["links"] += 1
        if r["rank"] is not None and (t["rank"] is None or r["rank"] > t["rank"]):
            t["strongest"], t["rank"] = r["site"], r["rank"]
    out = [{"url": t["url"], "domains": len(t["domains"]), "links": t["links"], "sites": sorted(t["domains"]),
            "strongest": t["strongest"] or min(t["domains"]), "rank": t["rank"]} for t in found.values()]
    return sorted(out, key=lambda t: (-t["domains"], -t["links"], t["url"]))


def status(url: str) -> dict:
    """{"url", "state", "status", "final"}: state is "live", "redirected" (to final), "dead" (404 or 410, also
    at the end of a redirect chain), "blocked" (any other HTTP error) or "unreachable" (no answer)."""
    got = page.fetch(url)
    final = got.get("final") or url
    if got["status"] in page.GONE:
        state = "dead"
    elif got["blocked"]:
        state = "blocked"
    elif got["dead"]:
        state = "unreachable"
    else:
        state = "redirected" if links.clean(final) != links.clean(url) else "live"
    return {"url": url, "state": state, "status": got["status"], "final": final, "error": got.get("error", "")}


def sitemap_urls(domain: str, files: int = SITEMAP_FILES, cap: int = SITEMAP_URLS) -> list[str]:
    """The pages your own sitemaps list: the sitemaps named in robots.txt, else /sitemap.xml; indexes followed
    (nested ones too) until `files` files are read; at most `cap` URLs, on your own site only."""
    robots = page.fetch(f"https://{domain}/robots.txt")
    queue = SITEMAP_LINE.findall(robots["html"] if not (robots["dead"] or robots["blocked"]) else "")
    queue = queue or [f"https://{domain}/sitemap.xml"]
    own, found, read, asked = page.registrable(domain), {}, 0, set()
    while queue and read < files and len(found) < cap:
        url = queue.pop(0)
        if url in asked or url.lower().endswith(".gz"):         # a gzipped sitemap is not read
            continue
        asked.add(url)
        got, read = page.fetch(url), read + 1
        if got["dead"] or got["blocked"]:
            continue
        locs = [u.replace("&amp;", "&") for u in LOC.findall(got["html"])]
        if "<sitemapindex" in got["html"]:
            queue += locs
        else:
            found.update(dict.fromkeys(u for u in locs if page.registrable(u) == own))
    return list(found)[:cap]


def tokens(path: str) -> list[str]:
    """The words of a path: "/blog/Old_Post-name.html" -> ["blog", "old", "post", "name"]."""
    words = re.split(r"[/\-_.~+%\s]+", urllib.parse.unquote(path).lower())
    return [w for w in words if w and w not in EXTENSIONS]


def _alike(a: str, b: str) -> bool:
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


def token_score(a: list[str], b: list[str]) -> float:
    """Dice overlap of two paths' words, "install" matching "installation"."""
    if not a or not b:
        return 0.0
    shared = sum(1 for x in a if any(_alike(x, y) for y in b))
    return 2 * min(shared, len(b)) / (len(a) + len(b))


def similarity(a: str, b: str) -> float:
    """How close two paths are, 0 to 1: their words (0.6) and their spelling (0.4)."""
    words = token_score(tokens(a), tokens(b))
    spelling = SequenceMatcher(None, a.strip("/").lower(), b.strip("/").lower()).ratio()
    return round(0.6 * words + 0.4 * spelling, 2)


def suggest(dead: str, candidates: list[str], check=status) -> dict:
    """{"url", "score"}: the live page closest to `dead`, or url "" with the best score found when none
    reaches MATCH_MIN. Up to TRIES candidates are checked; one that redirects is suggested at its end."""
    path, mine = urllib.parse.urlsplit(dead).path, tokens(urllib.parse.urlsplit(dead).path)
    others = [c for c in candidates if links.clean(c) != links.clean(dead)]
    quick = sorted(others, key=lambda c: -token_score(mine, tokens(urllib.parse.urlsplit(c).path)))[:SHORTLIST]
    scored = sorted(((similarity(path, urllib.parse.urlsplit(c).path), c) for c in quick), key=lambda p: (-p[0], len(p[1])))
    for score, url in scored[:TRIES]:
        if score < MATCH_MIN:
            break
        got = check(url)
        if got["state"] in ("live", "redirected"):
            return {"url": got["final"] if got["state"] == "redirected" else url, "score": score}
    return {"url": "", "score": scored[0][0] if scored else 0.0}


def dead_flag(dead: list[dict]) -> dict | None:
    if not dead:
        return None
    domains = len({s for d in dead for s in d["sites"]})
    worst = "; ".join(f"{urllib.parse.urlsplit(d['url']).path or '/'} ({d['status']}, {d['domains']} referring "
                      f"domain{'s' if d['domains'] != 1 else ''})" for d in dead[:3])
    return flag("dead_target", f"{len(dead)} page{'s' if len(dead) != 1 else ''} of yours answer 404 or 410 and have "
                               f"links from {domains} referring domain{'s' if domains != 1 else ''}: {worst}")


def lost(domain: str, fresh: bool = False, rows: int = links.ROWS, sitewide: int = links.SITEWIDE_PAGES,
         check=status, sitemap=sitemap_urls) -> dict:
    """{"domain", "read", "total", "domains", "source", "strength", "pages", "checked", "dead", "redirected",
    "blocked", "unreachable", "sitemap", "flags", "cost", "errors"}"""
    domain = page.host(domain)
    got = links.fetch(page.site(domain), fresh, rows)
    once = links.counted(got["rows"], links.sitewide(got["rows"], sitewide))
    found = targets(once, domain)
    asked = found[:CHECKED]
    with ThreadPoolExecutor(WORKERS) as pool:
        answers = list(pool.map(lambda t: check(t["url"]), asked))
    by_state = defaultdict(list)
    for t, a in zip(asked, answers):
        by_state[a["state"]].append({**t, **a})
    candidates = sitemap(domain) if by_state["dead"] else []
    for d in by_state["dead"]:
        d["suggest"] = suggest(d["url"], candidates, check)
    return {"domain": domain, "read": len(got["rows"]), "total": got["total"], "domains": links.domains(got["rows"]),
            "source": got["source"], "strength": got["strength"], "pages": len(found), "checked": len(asked),
            **{s: by_state[s] for s in ("dead", "redirected", "blocked", "unreachable")}, "sitemap": len(candidates),
            "flags": ranked([f for f in [dead_flag(by_state["dead"])] if f]), "cost": got["cost"], "errors": got["errors"]}
