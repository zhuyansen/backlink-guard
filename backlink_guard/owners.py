"""Sites linking to you that one owner runs (0.8): the referring domains whose home pages report to one analytics or
ads account.

vet groups the sites it checks by the accounts their home pages report to (vet.ids_of: AdSense publisher IDs, Google
Analytics and Tag Manager IDs, Clarity, the Facebook pixel) and keeps them across checks (seen.py). This does the same
for the sites that link to you: the home page of each referring domain, once, free, WORKERS at a time, at most
--homes of them. The referring domains are the ones in the backlinks read (links.fetch), the most links first; when
those hold fewer than --homes, AIsa's list of referring domains fills up the rest, strongest first (one call, about
$0.035 for 300): on 2026-10-20 a site's strongest 1,000 backlinks came from 29 referring domains, 949 of them from
three site-wide sources. NETWORK_MIN or more on one
account, counting the sites seen with it in earlier checks, are one owner's network: their links are one owner's
votes, not independent ones (lower value), and a network built to link is the pattern Google's spam policies describe
(higher risk). This run's accounts are kept for the next check, so a site vetted later is matched against them too.
A media group's titles or a platform's hosted sites can share an account honestly: read the sites before acting.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from . import aisa, blocklist, page, seen
from .policy import flag
from .vet import ids_of, paid, remember, shared_owners

WORKERS = 8             # home pages read at once, each on a different site
HOMES = 300             # referring domains whose home pages are read at most
NETWORK_MIN = 3         # sites on one account that make a network (vet flags two as "one owner" in a check)
LINKING_MIN = 2         # ... at least this many of them linking to you: one referring domain is one vote anyway
REFERRING_TOOL = "post_dataforseo_backlinks_referring_domains_live"


def by_links(rows: list[dict]) -> Counter:
    """{referring domain: links to you}."""
    return Counter(r["site"] for r in rows if r["site"])


def referring(domain: str, limit: int, fresh: bool) -> tuple[Counter, int]:
    """({referring domain: backlinks} for up to `limit` of them, strongest first, cost): AIsa's list, kept 7 days."""
    data, cost = paid("aisa", f"refdomains:{domain}:{limit}", lambda: aisa.call(REFERRING_TOOL, {
        "target": domain, "limit": limit, "order_by": ["rank,desc"], "backlinks_status_type": "live"}), fresh)
    return Counter({page.registrable(i["domain"]): int(i.get("backlinks") or 0) for i in (data or {}).get("items") or []
                    if i.get("domain")}), cost


def accounts_of(sites: list[str], fetch=None) -> dict[str, list[str]]:
    """{site: the accounts its home page reports to}; a site that does not answer reports to none. `fetch` is
    page.fetch unless given, looked up when called."""
    fetch = fetch or page.fetch
    with ThreadPoolExecutor(WORKERS) as pool:
        homes = list(pool.map(lambda s: fetch(f"https://{s}/"), sites))
    return {s: ids_of(h.get("html") or "") for s, h in zip(sites, homes)}


def listed_or_none(fresh: bool) -> tuple[dict | None, list[str]]:
    """(the shared spam-link list, errors); None when it cannot be read, never read as empty."""
    try:
        return blocklist.load(fresh), []
    except (OSError, ValueError) as exc:
        return None, [f"spam list: {exc}"]


def is_network(group: dict, here: dict) -> bool:
    """NETWORK_MIN or more sites on the account, counting earlier checks, LINKING_MIN or more of them linking to you."""
    return len(group["sites"]) >= NETWORK_MIN and sum(1 for s in group["sites"] if s in here) >= LINKING_MIN


def group_rows(groups: list[dict], here: dict[str, list[str]], links: Counter, listed: dict | None) -> list[dict]:
    """[{"key", "sites" (linking to you), "earlier", "links", "listed"}], the most sites first."""
    out = [{"key": g["key"], "sites": [s for s in g["sites"] if s in here], "earlier": [s for s in g["sites"] if s not in here],
            "links": sum(links[s] for s in g["sites"]), "listed": [s for s in g["sites"] if s in (listed or {})]}
           for g in groups]
    return sorted(out, key=lambda g: (-len(g["sites"]) - len(g["earlier"]), g["key"]))


def owner_flag(groups: list[dict]) -> dict | None:
    """One caution naming the networks, their sites and how many links they give."""
    if not groups:
        return None
    sites = len({s for g in groups for s in g["sites"]})
    parts = [f"{g['key']} on {', '.join(g['sites'][:4])}{' …' if len(g['sites']) > 4 else ''}"
             + (f" (and {len(g['earlier'])} from earlier checks)" if g["earlier"] else "") + f", {g['links']} links"
             for g in groups[:3]]
    more = f"; and {len(groups) - 3} more" if len(groups) > 3 else ""
    return flag("owner_network", f"{sites} referring domains in {len(groups)} network{'s' if len(groups) > 1 else ''}: "
                                 + "; ".join(parts) + more + ". Count each network as one source")


def networks(links: Counter, homes: int = HOMES, today: date | None = None, fresh: bool = False, fetch=None) -> dict:
    """{"read", "with_accounts", "groups", "flag", "networks" (blocklist report links), "errors"} for the referring
    domains in `links` ({site: links to you}), the most links first."""
    today = today or date.today()
    here = accounts_of([s for s, _ in sorted(links.items(), key=lambda kv: (-kv[1], kv[0]))][:homes], fetch)
    checked = [{"domain": s, "title": "", "flags": [], "metrics": {"ids": ids}} for s, ids in here.items()]
    store = seen.load()
    groups = shared_owners(checked, store["ids"])
    listed, errors = listed_or_none(fresh)
    for r in checked:
        r["flags"] += [f for f in [blocklist.flag_for(r["domain"], listed or {})] if f]
    errors += remember(checked, store, today)
    wide = [g for g in groups if is_network(g, here)]
    found = group_rows(wide, here, links, listed)
    return {"read": len(here), "with_accounts": sum(1 for ids in here.values() if ids), "groups": found,
            "flag": owner_flag(found), "networks": blocklist.unlisted(wide, checked, listed, today), "errors": errors}
