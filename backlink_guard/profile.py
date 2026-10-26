"""Your own link profile: what it looks like, and whether it is changing in a way that
reads as manufactured.

GoAnyAPI gives the totals and the top linking pages ($0.004). Glasser or AIsa gives
the weekly count of new and lost referring domains ($0.025), up to 1,000 of your backlinks
one by one (about $0.06: the anchors, the referring domains and the site-wide sources, see
links.py), and the spam score of the sites that link to you ($0.025 for the batch). With
--deep it also gives the full anchor distribution (about $0.04).

Every count of links comes with its count of referring domains, and a site that links to one
page of yours from many of its pages is counted once in the anchor shares.

The home pages of the referring domains are read too (free, owners.py): three or more on one
analytics or ads account are one owner's network, counted as one source.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from statistics import median

from . import aisa, backend, goanyapi, links, owners, page
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
    top = [{"from": b.get("urlFrom", ""), "to": b.get("urlTo") or "", "site": page.site(b.get("urlFrom", "")), "anchor": " ".join((b.get("anchor") or "").split()),
            "dr": b.get("domainRating"), "title": (b.get("title") or "")[:100]} for b in data.get("topBacklinks") or []]
    return totals, top, cost


def weekly(domain: str, today: date, fresh: bool) -> tuple[list[dict], int]:
    """[{"week", "new", "lost"}] oldest first, complete weeks only."""
    start = today - timedelta(weeks=WEEKS)
    result, cost = paid("aisa", f"newlost:{domain}:{today.isocalendar()[:2]}", lambda: backend.call(NEW_LOST_TOOL, {
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


def from_domains(entry: tuple) -> str:
    """" from 7 referring domains" when the anchor row carries its count of domains, else ""."""
    return f" from {entry[2]:,} referring domain{'s' if entry[2] != 1 else ''}" if len(entry) > 2 and entry[2] else ""


def anchor_flag(anchors: list[tuple], domain: str) -> dict | None:
    """anchors: [(text, links)] or [(text, links, referring domains)], a site-wide source counted once.
    A flag when one keyword anchor carries a large share of the links."""
    total = sum(a[1] for a in anchors)
    keyword = [a for a in anchors if kind_of(a[0], domain) == "keyword"]
    if total < ANCHOR_MIN or not keyword:
        return None
    top = max(keyword, key=lambda p: p[1])
    text, n = top[0], top[1]
    if n / total >= ANCHOR_SHARE:
        return flag("anchor_repeat", f"\"{text[:60]}\" on {n} of {total} links ({round(n / total * 100)}%){from_domains(top)}")
    return None


def spam_anchor_flag(anchors: list[tuple]) -> dict | None:
    """A flag when anchors pointing at you advertise links or belong to the usual spam trades.
    Someone else's network usually puts them there; knowing is the point, not blame."""
    hits = [a for a in anchors if LINK_SELLER.search(a[0]) or SPAM_WORDS.search(a[0])]
    if not hits:
        return None
    worst = sorted(hits, key=lambda p: -p[1])[:3]
    return flag("spam_anchor", "; ".join(f"\"{a[0][:70]}\" on {a[1]} links{from_domains(a)}" for a in worst))


def full_anchors(domain: str, fresh: bool) -> tuple[list[tuple[str, int, int]], int]:
    """[(anchor, links, referring domains)] from the anchor table (Glasser or AIsa), and the cost."""
    result, cost = paid("aisa", f"anchors:{domain}", lambda: backend.call(ANCHORS_TOOL, {
        "target": domain, "limit": ANCHOR_ROWS, "order_by": ["backlinks,desc"]}), fresh)
    return [(" ".join((i.get("anchor") or "").split()), int(i.get("backlinks") or 0), int(i.get("referring_domains") or 0))
            for i in result.get("items") or []], cost


def referrer_flag(top: list[dict], scores: dict[str, int]) -> tuple[dict | None, list[dict]]:
    """(flag or None, the linking sites that score high, worst first)."""
    sites = sorted({t["site"] for t in top if t["site"]})
    worst = sorted(({"site": s, "spam_score": scores[s]} for s in sites if (scores.get(s) or 0) >= SPAM_SCORE_HIGH),
                   key=lambda r: -r["spam_score"])
    if sites and len(worst) / len(sites) >= SPAMMY_SHARE:
        names = ", ".join(f"{w['site']} ({w['spam_score']})" for w in worst[:4])
        return flag("spammy_referrers", f"{len(worst)} of your top {len(sites)} linking sites: {names}"), worst
    return None, worst


def audit(domain: str, deep: bool = False, today: date | None = None, fresh: bool = False,
          sitewide: int = links.SITEWIDE_PAGES, rows: int = links.ROWS, homes: int = owners.HOMES) -> dict:
    """{"domain", "totals", "top", "links", "weeks", "anchors", "worst_referrers", "owners", "flags", "cost", "errors"}.
    "links": the backlinks read one by one ({"read", "domains", "total", "source", "sitewide"}); "anchors":
    [(text, links, referring domains)], a site-wide source counted once; "owners": the referring domains one owner
    runs ({"read", "with_accounts", "groups", "networks"}), up to `homes` home pages read, none when it is 0."""
    today, domain = today or date.today(), page.site(domain)
    out = {"domain": domain, "totals": {}, "top": [], "links": {}, "weeks": [], "anchors": [], "worst_referrers": [],
           "owners": {}, "flags": [], "cost": 0, "errors": []}
    steps = []
    if goanyapi.key():
        steps.append(("links", lambda: _links(out, domain, fresh)))
    steps.append(("backlinks", lambda: _rows(out, domain, fresh, sitewide, rows)))
    if backend.key():
        steps += [("weekly", lambda: _weekly(out, domain, today, fresh)), ("referrers", lambda: _referrers(out, fresh))]
        if deep:
            steps.append(("anchors", lambda: _anchors(out, domain, fresh)))
    for name, step in steps:
        try:
            step()
        except (goanyapi.GoAnyError, aisa.AisaError) as exc:
            out["errors"].append(f"{name}: {exc}")
    if homes > 0 and out["links"].get("rows"):
        _owners(out, domain, today, homes, fresh)
    if not deep and (out["links"].get("rows") or out["top"]):
        out["anchors"] = _sampled_anchors(out)
        out["flags"] += [f for f in [anchor_flag(out["anchors"], domain), spam_anchor_flag(out["anchors"])] if f]
    out["links"].pop("rows", None)
    out["flags"] = ranked(out["flags"])
    return out


def _sampled_anchors(out: dict) -> list[tuple[str, int, int]]:
    """The anchors of the backlinks read one by one, a site-wide source counted once; the top linking pages
    when none were read."""
    if out["links"].get("rows"):
        return links.anchors(out["links"]["rows"], out["links"]["sitewide"])
    counts, sites = Counter(t["anchor"] for t in out["top"]), {}
    for t in out["top"]:
        sites.setdefault(t["anchor"], set()).add(t["site"])
    return [(a, n, len(sites[a])) for a, n in counts.most_common()]


def _rows(out: dict, domain: str, fresh: bool, pages_min: int, limit: int) -> None:
    got = links.fetch(domain, fresh, limit, top=out["top"])
    out["cost"] += got["cost"]
    out["errors"] += got["errors"]
    if not got["rows"]:
        return
    groups = links.sitewide(got["rows"], pages_min)
    out["links"] = {"rows": got["rows"], "read": len(got["rows"]), "domains": links.domains(got["rows"]),
                    "total": got["total"], "source": got["source"], "sitewide": groups,
                    "counted_once": links.counted_once(groups)}
    out["flags"] += [f for f in [links.sitewide_flag(groups)] if f]


def _owners(out: dict, domain: str, today: date, homes: int, fresh: bool) -> None:
    """One owner's sites among the referring domains: their home pages read, free (owners.py). When the backlinks read
    name fewer than `homes` of them, the list of referring domains (Glasser or AIsa) fills up the rest."""
    sites = owners.by_links(out["links"]["rows"])
    if len(sites) < homes and backend.key():
        try:
            more, cost = owners.referring(domain, homes, fresh)
            out["cost"] += cost
            sites.update({s: n for s, n in more.items() if s not in sites})
        except aisa.AisaError as exc:
            out["errors"].append(f"referring domains: {exc}")
    got = owners.networks(sites, homes, today, fresh)
    out["owners"] = {k: got[k] for k in ("read", "with_accounts", "groups", "networks")}
    out["flags"] += [f for f in [got["flag"]] if f]
    out["errors"] += got["errors"]


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
    table, cost = full_anchors(domain, fresh)
    out["anchors"] = links.collapse(table, out["links"].get("sitewide") or [], out["links"].get("rows") or [])
    out["cost"] += cost
    out["flags"] += [f for f in [anchor_flag(out["anchors"], domain), spam_anchor_flag(out["anchors"])] if f]
