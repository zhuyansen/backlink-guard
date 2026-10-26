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

Pages of yours that redirect (0.8) are followed one hop at a time (page.trace) and judged, worst first:
broken (a loop, more than ten hops, or no page at the end), soft-lost (it ends on your home page, on
another site, or on a page whose path matches the old one under MATCH_MIN: Google's page on site moves
says such a redirect "might be treated as a soft 404", so the closest live page is suggested as for a
dead one), temporary (a 302, 303 or 307 on the way: Google keeps the old URL), chain (two hops or
more), or fine (one permanent hop to a page like it).
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
TEMPORARY = {302, 303, 307}
CHAIN = 2                   # redirects in a row that make a chain
# A home page: /, a language root (/zh/, /en-us) or an index file.
HOME = re.compile(r"^/(?:[a-z]{2}(?:[-_][a-z]{2,4})?/?)?(?:index\.(?:html?|php))?$", re.I)
VERDICTS = ("broken", "soft_lost", "temporary", "chain", "fine")       # worst first


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
    """{"url", "state", "status", "final", "error", "hops"}: state is "live", "redirected" (to final), "dead" (404 or
    410, also at the end of a redirect chain), "broken" (a redirect that loops, runs past ten hops or ends in no answer
    or another error), "blocked" (any other HTTP error) or "unreachable" (no answer)."""
    got = page.trace(url)
    if got["status"] in page.GONE:
        state = "dead"
    elif got["hops"] and got["error"]:
        state = "broken"
    elif got["error"]:
        state = "blocked" if got["status"] else "unreachable"
    else:
        state = "redirected" if got["hops"] else "live"
    return {"url": url, "state": state, "status": got["status"], "final": got["final"], "error": got["error"],
            "hops": got["hops"]}


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


def drift(d: dict, own: str) -> str:
    """Why a redirect lands where the link did not mean to go, "" when it does not: on another site, on your home page,
    or on a page whose path matches the old one under MATCH_MIN. A home page sent to a language root is fine."""
    start, end = urllib.parse.urlsplit(d["url"]).path or "/", urllib.parse.urlsplit(d["final"]).path or "/"
    if page.registrable(d["final"]) != page.registrable(own):
        return f"ends on another site, {page.host(d['final'])}"
    if HOME.match(start):
        return ""
    if HOME.match(end):
        return "ends on your home page"
    score = similarity(start, end)
    return f"ends on {end}, a path that matches it {score:.2f}" if score < MATCH_MIN else ""


def findings(d: dict, own: str) -> list[tuple[str, str]]:
    """[(verdict, why)] for a page of yours that redirects, worst first; [] when it is fine."""
    if d["state"] == "broken":
        return [("broken", d["error"] or "no page at the end")]
    found = []
    off = drift(d, own)
    if off:
        found.append(("soft_lost", off))
    temporary = [h["status"] for h in d["hops"] if h["status"] in TEMPORARY]
    if temporary:
        found.append(("temporary", f"{temporary[0]}, a temporary redirect"))
    if len(d["hops"]) >= CHAIN:
        found.append(("chain", f"{len(d['hops'])} redirects in a row"))
    return found


def judge(d: dict, own: str) -> dict:
    """The page with its "verdict" (the worst of VERDICTS found) and "why"."""
    found = findings(d, own)
    return {**d, "verdict": found[0][0] if found else "fine", "why": [w for _, w in found]}


def redirect_flags(redirects: list[dict]) -> list[dict]:
    """A note for each kind of redirect that costs links: soft-lost, temporary or chained, broken."""
    kinds = (("soft_lost", {"soft_lost"}), ("weak_redirect", {"temporary", "chain"}), ("broken_redirect", {"broken"}))
    out = []
    for name, verdicts in kinds:
        hit = [d for d in redirects if d["verdict"] in verdicts]
        if hit:
            domains = len({s for d in hit for s in d["sites"]})
            worst = "; ".join(f"{urllib.parse.urlsplit(d['url']).path or '/'}: {', '.join(d['why'])}" for d in hit[:3])
            out.append(flag(name, f"{len(hit)} page{'s' if len(hit) != 1 else ''} of yours, linked from {domains} referring "
                                  f"domain{'s' if domains != 1 else ''}: {worst}"))
    return out


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
    """{"domain", "read", "total", "domains", "source", "strength", "pages", "checked", "dead", "redirected" (with
    "verdict", "why" and, when soft-lost, "suggest"; "broken" ones among them), "blocked", "unreachable", "sitemap",
    "flags", "cost", "errors"}"""
    domain = page.host(domain)
    got = links.fetch(page.site(domain), fresh, rows)
    once = links.counted(got["rows"], links.sitewide(got["rows"], sitewide))
    found = targets(once, domain)
    by_state = asked_all(found[:CHECKED], check)
    moved = sorted((judge(d, domain) for d in by_state["redirected"] + by_state["broken"]),
                   key=lambda d: (VERDICTS.index(d["verdict"]), -d["domains"], d["url"]))
    gone = by_state["dead"] + [d for d in moved if d["verdict"] == "soft_lost"]
    candidates = sitemap(domain) if gone else []
    for d in gone:
        d["suggest"] = suggest(d["url"], candidates, check)
    flags = [f for f in [dead_flag(by_state["dead"])] if f] + redirect_flags(moved)
    return {"domain": domain, "read": len(got["rows"]), "total": got["total"], "domains": links.domains(got["rows"]),
            "source": got["source"], "strength": got["strength"], "pages": len(found), "checked": min(len(found), CHECKED),
            "dead": by_state["dead"], "redirected": moved, "blocked": by_state["blocked"],
            "unreachable": by_state["unreachable"], "sitemap": len(candidates), "flags": ranked(flags), "cost": got["cost"],
            "errors": got["errors"]}


def asked_all(asked: list[dict], check) -> dict[str, list[dict]]:
    """{state: [target with its answer]}: every page asked, WORKERS at a time."""
    with ThreadPoolExecutor(WORKERS) as pool:
        answers = list(pool.map(lambda t: check(t["url"]), asked))
    by_state: dict[str, list[dict]] = defaultdict(list)
    for t, a in zip(asked, answers):
        by_state[a["state"]].append({**t, **a})
    return by_state
