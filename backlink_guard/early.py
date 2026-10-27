"""Your competitors' earliest links: the channels they used at launch, which take a new site (0.11).

Sorted by the day the backlink index first found them, a competitor's referring domains begin with what it got in
its first weeks: directories, launch sites, lists and communities that take new sites, unlike the strong sites that
link to it today. For each competitor, and for your own site to compare:

- its launch: the Wayback Machine's first copy, or its first referring domain when that is earlier, or when it came
  more than DORMANT_DAYS after the first copy (the domain sat unused or parked before);
- its earliest ROWS_MAX referring domains, lost ones too (Glasser or AIsa, one call, about $0.06): how many it had
  30, 60 and 90 days after launch, against you at the same age, and the weeks that brought BURST_RATIO times the
  usual (launch week, often: the sites in it are the launch channels);
- those first seen in its first WINDOW days, still live and followed: the channels, without the site-wide links
  (one site linking from its footer or from SITEWIDE_ANY pages or more: mostly the owner's other sites and
  partners, not channels; named) and without what competitors.cleaned leaves out (the shared spam-link list, links
  scoring 50 or more for spam, one network's template pages);
- the channels two or more competitors share and you lack: a launch checklist, each with a linking page (one call a
  competitor), the youngest competitor it linked to (under YOUNG_DAYS old; first seen in the last RECENT_DAYS, it
  still takes new sites), and a free vet of the first VETTED, with newcomers.takes_new.

First seen is when the index found a link, which can be later than the link itself. The index begins on 2019-01-15,
so a competitor older than that shows the index's first crawl, not its launch: said so, with the advice to compare
against younger competitors.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from statistics import median

from . import aisa, backend, competitors, page
from .budget import Budget, OverBudget
from .links import TEMPLATE_PAGES, TEMPLATE_SHARE
from .vet import TEMPLATE_PLACES
from .vet import first_seen as first_copy

WINDOW = 90             # days after launch that count as early
AGES = (30, 60, 90)     # days after launch the referring domains are counted at
DORMANT_DAYS = 180      # a first referring domain this long after the first archived copy: the domain sat unused
INDEX_START = date(2019, 1, 15)     # the earliest first_seen in the backlink index (an old domain's list, 2026-10-27)
INDEX_EDGE = 31         # a first referring domain this close to the index's start: the index's first crawl
SITEWIDE_ANY = 100      # pages of one site linking to the competitor, wherever they sit: a site-wide link
BURST_MIN = 5           # new referring domains a week must bring to be a burst ...
BURST_RATIO = 3         # ... and this many times the usual week
YOUNG_DAYS = 90         # a competitor this young when a source first linked to it ...
RECENT_DAYS = 183       # ... in the last half year: the source still takes new sites
VETTED = 10             # checklist sites vetted, free
MAX_USD = 0.50          # three competitors and you: about $0.35


def day(stamp: str | None) -> date | None:
    try:
        return date.fromisoformat((stamp or "")[:10])
    except ValueError:
        return None


def earliest(target: str, budget: Budget, fresh: bool) -> tuple[list[dict], int]:
    """(the target's earliest referring domains, lost ones too, oldest first, ROWS_MAX at most; how many it has)."""
    body = {"target": target, "limit": competitors.ROWS_MAX, "order_by": ["first_seen,asc"], "backlinks_status_type": "all"}
    data, _ = budget.ask(f"aisa:refdomains-earliest:{target}:{competitors.ROWS_MAX}", competitors.estimate(competitors.ROWS_MAX),
                         lambda: backend.rest(competitors.REFERRING, body), fresh, f"the earliest referring domains of {target}")
    items = [i for i in (data or {}).get("items") or [] if i.get("domain") and day(i.get("first_seen"))]
    return sorted(items, key=lambda i: i["first_seen"]), int((data or {}).get("total_count") or len(items))


def followed(item: dict) -> bool:
    """At least one of the site's pages links to the competitor without nofollow."""
    return (item.get("referring_pages") or 0) > (item.get("referring_pages_nofollow") or 0)


def sitewide(item: dict) -> bool:
    """One site linking from SITEWIDE_ANY pages or more, or from TEMPLATE_PAGES or more with most of its links in a
    footer, navigation, header or sidebar (the index's semantic locations)."""
    pages, places = item.get("referring_pages") or 0, item.get("referring_links_semantic_locations") or {}
    total = sum(places.values())
    template = sum(n for where, n in places.items() if where in TEMPLATE_PLACES)
    return pages >= SITEWIDE_ANY or (pages >= TEMPLATE_PAGES and total > 0 and template / total >= TEMPLATE_SHARE)


def launch(domain: str, items: list[dict], archived: date | None) -> dict:
    """{"day", "from": "archive" | "first link" | "", "archived", "first_link", "dormant", "before_index"}."""
    first_link = day(items[0]["first_seen"]) if items else None
    dormant = bool(archived and first_link and (first_link - archived).days > DORMANT_DAYS)
    if archived and not dormant and (not first_link or archived <= first_link):
        start, source = archived, "archive"
    else:
        start, source = first_link, ("first link" if first_link else "")
    before = bool((archived and archived < INDEX_START)
                  or (first_link and first_link <= INDEX_START + timedelta(days=INDEX_EDGE)))
    return {"day": start.isoformat() if start else "", "from": source, "archived": archived.isoformat() if archived else "",
            "first_link": first_link.isoformat() if first_link else "", "dormant": dormant, "before_index": before}


def counts(items: list[dict], start: date, total: int) -> dict[int, dict]:
    """{age: {"n", "exact"}}: the referring domains first seen before `age` days after launch. When the list read
    stops before that day and the site has more, the count is a floor."""
    last = day(items[-1]["first_seen"]) if items else None
    complete = len(items) >= total
    out = {}
    for age in AGES:
        edge = start + timedelta(days=age)
        out[age] = {"n": sum(1 for i in items if day(i["first_seen"]) < edge),
                    "exact": complete or bool(last and last >= edge)}
    return out


def bursts(items: list[dict], start: date) -> list[dict]:
    """[{"week", "from", "n", "sites"}]: the weeks of the first WINDOW days that brought BURST_MIN new referring
    domains or more and BURST_RATIO times the usual week (the median, taken as one when it is zero)."""
    weeks = -(-WINDOW // 7)
    by_week: dict[int, list[str]] = {}
    for i in items:
        age = (day(i["first_seen"]) - start).days
        if 0 <= age < WINDOW:
            by_week.setdefault(age // 7, []).append(i["domain"])
    usual = max(median(len(by_week.get(w, [])) for w in range(weeks)), 1)
    return [{"week": w + 1, "from": (start + timedelta(days=7 * w)).isoformat(), "n": len(sites), "sites": sites}
            for w, sites in sorted(by_week.items()) if len(sites) >= BURST_MIN and len(sites) >= BURST_RATIO * usual]


def early_rows(rival: str, items: list[dict], start: date) -> tuple[list[dict], dict]:
    """(the rows first seen in the first WINDOW days that are live, followed and not site-wide, as competitors'
    rows; {"lost", "nofollow", "sitewide": [sites]} for the rest)."""
    edge = start + timedelta(days=WINDOW)
    rows, rest = [], {"lost": 0, "nofollow": 0, "sitewide": []}
    for i in (i for i in items if day(i["first_seen"]) < edge):
        if i.get("lost_date"):
            rest["lost"] += 1
        elif not followed(i):
            rest["nofollow"] += 1
        elif sitewide(i):
            rest["sitewide"].append(page.registrable(i["domain"]))
        else:
            rows.append(competitors.site_row(i["domain"], i.get("rank"), i["first_seen"], [rival], i.get("backlinks_spam_score")))
    rest["sitewide"] = sorted(set(rest["sitewide"]))
    return rows, rest


def young_links(rows: list[dict], rival: str, start: date, today: date) -> dict[str, dict]:
    """{site: {"rival", "age_days", "on", "recent"}}: the rows that linked to the rival under YOUNG_DAYS old; recent
    when that was in the last RECENT_DAYS, and the site still takes new sites."""
    found = {}
    for r in rows:
        seen = day(r["first_seen"])
        if seen and 0 <= (seen - start).days < YOUNG_DAYS:
            found[r["site"]] = {"rival": rival, "age_days": (seen - start).days, "on": seen.isoformat(),
                                "recent": (today - seen).days <= RECENT_DAYS}
    return found


def better(link: dict, held: dict | None) -> bool:
    """A recent link first, then the youngest competitor."""
    return held is None or (not link["recent"], link["age_days"]) < (not held["recent"], held["age_days"])


def checklist(tables: dict[str, list[dict]]) -> list[dict]:
    """The sites in two or more competitors' early tables, the most competitors first, then the earliest; with one
    competitor, its own table."""
    rows = competitors.merged([r for rows in tables.values() for r in rows])
    if len(tables) > 1:
        rows = [r for r in rows if len(r["rivals"]) >= 2]
    return sorted(rows, key=lambda r: (-len(r["rivals"]), r["first_seen"], r["site"]))


def early(own: str, rivals: list[str], max_usd: float = MAX_USD, vetted: int = VETTED, fresh: bool = False,
          today: date | None = None) -> dict:
    """{"domain", "rivals", "window", "sites": {site: {"launch", "total", "read", "counts", "bursts", "rows", "rest",
    "yours"}}, "checklist": [rows], "dropped", "networks", "vetted", "cost", "max_usd", "left_out", "errors"}. Your
    site comes first in "sites", with no "rows". A row: competitors' row plus "young" and, vetted, "vet"."""
    own, today = page.site(own), today or date.today()
    rivals = [r for r in dict.fromkeys(page.site(x) for x in rivals) if r and r != own][:competitors.RIVALS_MAX]
    out = {"domain": own, "rivals": rivals, "window": WINDOW, "sites": {}, "checklist": [], "dropped": [], "networks": [],
           "vetted": 0, "cost": 0, "max_usd": max_usd, "left_out": [], "errors": []}
    budget, read = Budget(max_usd), {}
    listed = competitors.listed_or_none(out, fresh)
    for site in [own] + rivals:
        _site(out, read, site, budget, fresh)
    _tables(out, read, listed or {}, today)
    _drop_yours(out, read, budget, fresh)
    _pages(out, budget, fresh, listed, today)
    if vetted:
        _vet(out, vetted, fresh, today)
    out.update(cost=budget.spent, left_out=budget.left_out)
    return out


def _site(out: dict, read: dict, site: str, budget: Budget, fresh: bool) -> None:
    try:
        items, total = earliest(site, budget, fresh)
    except OverBudget:
        return
    except aisa.AisaError as exc:
        out["errors"].append(f"earliest referring domains of {site}: {exc}")
        return
    when = launch(site, items, day(first_copy(site)))
    start = day(when["day"])
    read[site] = (items, start)
    out["sites"][site] = {"launch": when, "total": total, "read": len(items), "rows": [], "rest": {},
                          "counts": counts(items, start, total) if start else {}, "bursts": bursts(items, start) if start else []}


def _tables(out: dict, read: dict, listed: dict, today: date) -> None:
    """Each competitor's early channels, cleaned, and the checklist they share."""
    skip, young, tables = {out["domain"], *out["rivals"]}, {}, {}
    for rival in (r for r in out["rivals"] if read.get(r) and read[r][1]):
        items, start = read[rival]
        rows, rest = early_rows(rival, items, start)
        kept, gone = competitors.cleaned(competitors.merged(rows), skip, listed)
        competitors.add_dropped(out, gone)
        out["sites"][rival].update(rows=sorted(kept, key=lambda r: (r["first_seen"], r["site"])), rest=rest)
        tables[rival] = out["sites"][rival]["rows"]
        for site, link in young_links(kept, rival, start, today).items():
            if better(link, young.get(site)):
                young[site] = link
    out["checklist"] = checklist(tables)
    for rows in [out["checklist"], *tables.values()]:
        for r in rows:
            r["young"] = young.get(r["site"])


def _drop_yours(out: dict, read: dict, budget: Budget, fresh: bool) -> None:
    """Takes the sites that already link to you out of the tables and names them: from your own list when it was
    read in full, else asked (one call)."""
    items = read.get(out["domain"], ([], None))[0]
    yours = {page.registrable(i["domain"]) for i in items if not i.get("lost_date")}
    mine = out["sites"].get(out["domain"])
    if mine and mine["read"] < mine["total"]:
        hosts = [h for rows in tables_of(out) for r in rows for h in r["hosts"]]
        try:
            yours |= competitors.linking_you(out["domain"], hosts, budget, fresh)
        except OverBudget:
            pass
        except aisa.AisaError as exc:
            out["errors"].append(f"which sites already link to {out['domain']}: {exc}")
    for block in [b for s, b in out["sites"].items() if s != out["domain"]]:
        block["yours"] = sorted(r["site"] for r in block["rows"] if r["site"] in yours)
        block["rows"] = [r for r in block["rows"] if r["site"] not in yours]
    out["checklist"] = [r for r in out["checklist"] if r["site"] not in yours]


def tables_of(out: dict) -> list[list[dict]]:
    return [b["rows"] for s, b in out["sites"].items() if s != out["domain"]] + [out["checklist"]]


def _pages(out: dict, budget: Budget, fresh: bool, listed: dict | None, today: date) -> None:
    """A linking page for the first rows of each table (one call a competitor), what kind of page it is, and one
    network's template pages taken out (competitors.networks)."""
    wanted: dict[str, set[str]] = {}
    for rival in out["rivals"]:
        for r in out["sites"].get(rival, {}).get("rows", [])[:competitors.LOOKED_UP]:
            wanted.setdefault(rival, set()).update(r["hosts"])
    for r in out["checklist"][:competitors.LOOKED_UP]:
        wanted.setdefault(r["rivals"][0], set()).update(r["hosts"])
    pages: dict[str, dict] = {}
    for rival, hosts in wanted.items():
        try:
            pages.update({k: v for k, v in competitors.examples(rival, sorted(hosts), budget, fresh).items() if k not in pages})
        except OverBudget:
            continue
        except aisa.AisaError as exc:
            out["errors"].append(f"linking pages of {rival}: {exc}")
    for rows in tables_of(out):
        competitors.annotate(rows, pages)
    members = competitors.drop_networks(out, tables_of(out), listed, today)
    for block in (b for s, b in out["sites"].items() if s != out["domain"]):
        block["rows"] = [r for r in block["rows"] if r["site"] not in members]
    out["checklist"] = [r for r in out["checklist"] if r["site"] not in members]


def _vet(out: dict, limit: int, fresh: bool, today: date) -> None:
    """A free vet (the sites' own pages, and whether their newest pages link to new sites) of the first `limit`
    checklist sites."""
    from .vet import vet as vetting

    sites = [r["site"] for r in out["checklist"][:limit]]
    if not sites:
        return
    found = {v["domain"]: v for v in vetting(sites, paid_sources=False, today=today, fresh=fresh, newcomers=True)["rows"]}
    for r in out["checklist"]:
        v = found.get(r["site"])
        r["vet"] = {"grade": v.get("grade"), "action": v.get("action"), "takes_new": v.get("newcomers")} if v else None
    out["vetted"] = len(found)
