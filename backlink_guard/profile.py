"""Your own link profile: what it looks like, and whether it is changing in a way that
reads as manufactured.

GoAnyAPI gives the totals and the top linking pages ($0.004). AIsa (DataForSEO) gives
the weekly count of new and lost referring domains ($0.025), and the spam score of the
sites that link to you ($0.025 for the batch). With --deep it also gives the full anchor
distribution (about $0.04).
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from statistics import median

from . import aisa, goanyapi, page
from .policy import flag, ranked
from .vet import SPAM_SCORE_HIGH, SPAM_WORDS, paid, spam_scores

NEW_LOST_TOOL = "post_dataforseo_backlinks_timeseries_new_lost_live"
ANCHORS_TOOL = "post_dataforseo_backlinks_anchors_live"
WEEKS = 16                  # how far back the weekly series goes
BASE_WEEKS = 8              # the weeks a new week is compared with
SPIKE = 3.0                 # times the usual week
SPIKE_MIN = 10              # new referring domains; under this a spike is two or three links
ANCHOR_SHARE = 0.3          # one keyword anchor on this share of links
ANCHOR_MIN = 10             # links needed before a share means anything
SPAMMY_SHARE = 0.25         # of the top linking sites
FEW_FOLLOWED = 0.05         # followed referring domains over all referring domains
ANCHOR_ROWS = 100
LINK_SELLER = re.compile(r"\bpbn\b|do-?follow backlinks?|buy backlinks?|backlinks? (?:service|package)|\bda ?\d{2}\b.*\bpa ?\d{2}\b", re.I)
GENERIC = re.compile(r"^(?:click here|here|visit(?: (?:site|website))?|website|link|try now|learn more|read more|"
                     r"check detail|open in new tab|source|homepage|访问网站|官网|查看详情)?$", re.I)


def summary(domain: str, fresh: bool) -> tuple[dict, list[dict], int]:
    """(totals, top linking pages, cost) from GoAnyAPI."""
    data, cost = paid("goanyapi", f"backlink:{domain}", lambda: goanyapi.call("backlink", domain=domain), fresh)
    totals = {"dr": data.get("domainRating"), "backlinks": data.get("backlinks"), "refdomains": data.get("refdomains"),
              "followed_backlinks": data.get("dofollowBacklinks"), "followed_refdomains": data.get("dofollowRefdomains")}
    top = [{"from": b.get("urlFrom", ""), "site": page.site(b.get("urlFrom", "")), "anchor": " ".join((b.get("anchor") or "").split()),
            "dr": b.get("domainRating"), "title": (b.get("title") or "")[:100]} for b in data.get("topBacklinks") or []]
    return totals, top, cost


def weekly(domain: str, today: date, fresh: bool) -> tuple[list[dict], int]:
    """[{"week", "new", "lost"}] oldest first, complete weeks only."""
    start = today - timedelta(weeks=WEEKS)
    result, cost = paid("aisa", f"newlost:{domain}:{today.isocalendar()[:2]}", lambda: aisa.call(NEW_LOST_TOOL, {
        "target": domain, "date_from": start.isoformat(), "date_to": today.isoformat(), "group_range": "week"}), fresh)
    rows = [{"week": (i.get("date") or "")[:10], "new": int(i.get("new_referring_domains") or 0),
             "lost": int(i.get("lost_referring_domains") or 0)} for i in result.get("items") or []]
    return [r for r in rows if r["week"] and r["week"] <= today.isoformat()], cost


def velocity(weeks: list[dict]) -> dict | None:
    """A flag when the latest week brought far more new referring domains than the weeks before it."""
    if len(weeks) < BASE_WEEKS + 1:
        return None
    latest, base = weeks[-1], median(w["new"] for w in weeks[-1 - BASE_WEEKS:-1])
    if latest["new"] >= SPIKE_MIN and latest["new"] >= SPIKE * max(base, 1):
        return flag("velocity_spike", f"{latest['new']} new referring domains in the week to {latest['week']}; "
                                      f"the eight weeks before had {base:g} in a typical week")
    return None


def kind_of(anchor: str, domain: str) -> str:
    """"brand", "url", "generic" or "keyword"."""
    text, stem = anchor.lower().strip(), domain.split(".")[0].lower()
    if not text or GENERIC.match(text):
        return "generic"
    if domain.lower() in text or text.startswith(("http://", "https://", "www.")):
        return "url"
    return "brand" if stem in re.sub(r"[\s\-_]+", "", text) else "keyword"


def anchor_flag(anchors: list[tuple[str, int]], domain: str) -> dict | None:
    """anchors: [(text, links)]. A flag when one keyword anchor carries a large share of the links."""
    total = sum(n for _, n in anchors)
    keyword = [(a, n) for a, n in anchors if kind_of(a, domain) == "keyword"]
    if total < ANCHOR_MIN or not keyword:
        return None
    text, n = max(keyword, key=lambda p: p[1])
    if n / total >= ANCHOR_SHARE:
        return flag("anchor_repeat", f"\"{text[:60]}\" on {n} of {total} links ({round(n / total * 100)}%)")
    return None


def spam_anchor_flag(anchors: list[tuple[str, int]]) -> dict | None:
    """A flag when anchors pointing at you advertise links or belong to the usual spam trades.
    Someone else's network usually puts them there; knowing is the point, not blame."""
    hits = [(a, n) for a, n in anchors if LINK_SELLER.search(a) or SPAM_WORDS.search(a)]
    if not hits:
        return None
    worst = sorted(hits, key=lambda p: -p[1])[:3]
    return flag("spam_anchor", "; ".join(f"\"{a[:70]}\" on {n} links" for a, n in worst))


def full_anchors(domain: str, fresh: bool) -> tuple[list[tuple[str, int]], int]:
    result, cost = paid("aisa", f"anchors:{domain}", lambda: aisa.call(ANCHORS_TOOL, {
        "target": domain, "limit": ANCHOR_ROWS, "order_by": ["backlinks,desc"]}), fresh)
    return [(" ".join((i.get("anchor") or "").split()), int(i.get("backlinks") or 0)) for i in result.get("items") or []], cost


def referrer_flag(top: list[dict], scores: dict[str, int]) -> tuple[dict | None, list[dict]]:
    """(flag or None, the linking sites that score high, worst first)."""
    sites = sorted({t["site"] for t in top if t["site"]})
    worst = sorted(({"site": s, "spam_score": scores[s]} for s in sites if (scores.get(s) or 0) >= SPAM_SCORE_HIGH),
                   key=lambda r: -r["spam_score"])
    if sites and len(worst) / len(sites) >= SPAMMY_SHARE:
        names = ", ".join(f"{w['site']} ({w['spam_score']})" for w in worst[:4])
        return flag("spammy_referrers", f"{len(worst)} of your top {len(sites)} linking sites: {names}"), worst
    return None, worst


def audit(domain: str, deep: bool = False, today: date | None = None, fresh: bool = False) -> dict:
    """{"domain", "totals", "top", "weeks", "anchors", "worst_referrers", "flags", "cost", "errors"}"""
    today, domain = today or date.today(), page.site(domain)
    out = {"domain": domain, "totals": {}, "top": [], "weeks": [], "anchors": [], "worst_referrers": [], "flags": [],
           "cost": 0, "errors": []}
    steps = []
    if goanyapi.key():
        steps.append(("links", lambda: _links(out, domain, fresh)))
    if aisa.key():
        steps += [("weekly", lambda: _weekly(out, domain, today, fresh)), ("referrers", lambda: _referrers(out, fresh))]
        if deep:
            steps.append(("anchors", lambda: _anchors(out, domain, fresh)))
    for name, step in steps:
        try:
            step()
        except (goanyapi.GoAnyError, aisa.AisaError) as exc:
            out["errors"].append(f"{name}: {exc}")
    if not deep and out["top"]:
        counts = Counter(t["anchor"] for t in out["top"])
        out["anchors"] = counts.most_common()
        out["flags"] += [f for f in [anchor_flag(out["anchors"], domain), spam_anchor_flag(out["anchors"])] if f]
    out["flags"] = ranked(out["flags"])
    return out


def _links(out: dict, domain: str, fresh: bool) -> None:
    out["totals"], out["top"], cost = summary(domain, fresh)
    out["cost"] += cost
    all_, followed = out["totals"].get("refdomains") or 0, out["totals"].get("followed_refdomains") or 0
    if all_ and followed / all_ < FEW_FOLLOWED:
        out["flags"].append(flag("few_followed", f"{followed} of {all_} referring domains pass ranking credit"))


def _weekly(out: dict, domain: str, today: date, fresh: bool) -> None:
    out["weeks"], cost = weekly(domain, today, fresh)
    out["cost"] += cost
    out["flags"] += [f for f in [velocity(out["weeks"])] if f]


def _referrers(out: dict, fresh: bool) -> None:
    sites = sorted({t["site"] for t in out["top"] if t["site"]})
    if not sites:
        return
    scores, cost = spam_scores(sites, fresh)
    out["cost"] += cost
    found, out["worst_referrers"] = referrer_flag(out["top"], scores)
    out["flags"] += [f for f in [found] if f]


def _anchors(out: dict, domain: str, fresh: bool) -> None:
    out["anchors"], cost = full_anchors(domain, fresh)
    out["cost"] += cost
    out["flags"] += [f for f in [anchor_flag(out["anchors"], domain), spam_anchor_flag(out["anchors"])] if f]
