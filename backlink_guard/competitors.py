"""Links your competitors earned and you have not (0.8): each competitor's new referring domains, and the sites that
link to two or more of them but not to you, the link intersect.

The point is earned links. The directories, lists and articles that cover your field already name your competitors,
so the people who run them are the ones to tell about what you make: submit where it fits, ask to be added to a list,
offer an author what the page lacks. Nothing here is a link to buy.

From the backlink data (Glasser or AIsa), at about $0.024 a call plus $0.000036 a row (seen 2026-10-20, the same on both):
- each competitor's referring domains first seen in the last --days days, strongest first: one call each;
- which of those already link to you: one call for all of them;
- the link intersect: the domain intersection in its "partial" mode, with your domain excluded. Its page
  says each row links to all the targets; tried on 2026-10-20 with three, partial mode returned the domains linking
  to two or three of them (86 in all), so one call covers "two or more";
- one linking page for each site shown: one call per competitor that has any.
--max-usd caps the run (budget.py).

Left out, and named: your site and the competitors themselves when they link to each other; the sites on the shared
spam-link list; the sites whose links to the competitor score 50 or more for spam (each row of the lists
carries it; vet counts a site's own score from 50); and NETWORK_MIN or more sites whose linking pages share one title,
each site's own name taken out (vet.templates): one network's template, not places that chose to cover the field. On
2026-10-20, 86 of one competitor's 100 newest referring domains were such pages, all scoring 45 or 55, against 0 to
30 for the rest.
"""
from __future__ import annotations

from datetime import date, timedelta

from . import aisa, backend, blocklist, find, page
from .budget import Budget, OverBudget
from .vet import SPAM_SCORE_HIGH, templates

REFERRING = "backlinks/referring_domains/live"      # AIsa's passthrough: the tool router refuses array filters
INTERSECTION = "backlinks/domain_intersection/live"
BACKLINKS = "backlinks/backlinks/live"
DAYS = 7
LIMIT = 100             # referring domains read from each list; the most is 1,000
ROWS_MAX = 1000
SHOWN = 25              # sites a table shows
LOOKED_UP = 2 * SHOWN   # sites a linking page is looked up for: one call per competitor whatever their number, and a
                        # network's pages taken out of a table (12 of one competitor's first 25 on 2026-10-20) leave
                        # sites with pages to show
MAX_USD = 0.30          # three competitors cost about $0.20 at most
RIVALS_MAX = 20         # the most targets the intersection takes
CALL = 24_000           # micro-USD a backlinks call costs before its rows (20 rows: $0.0247, 2026-10-20)
ROW = 36                # micro-USD a row
NETWORK_MIN = 3         # sites sharing one linking-page title that make a network


def estimate(rows: int) -> int:
    """The most a call returning up to `rows` rows costs."""
    return CALL + ROW * rows


def since(today: date, days: int) -> str:
    """The first_seen filter's form of the day `days` before today."""
    return f"{(today - timedelta(days=days)).isoformat()} 00:00:00 +00:00"


def site_row(host: str, rank, first_seen: str, rivals: list[str], spam=None) -> dict:
    """`spam`: the spam score of the site's links to the competitor (its backlinks_spam_score)."""
    return {"site": page.registrable(host), "hosts": [host], "rank": rank, "first_seen": (first_seen or "")[:10],
            "rivals": rivals, "spam": spam}


def new_domains(rival: str, start: str, limit: int, budget: Budget, fresh: bool) -> tuple[list[dict], int]:
    """(the rival's referring domains first seen on or after `start`, strongest first; how many there are in all)."""
    body = {"target": rival, "limit": limit, "order_by": ["rank,desc"], "backlinks_status_type": "live",
            "filters": [["first_seen", ">=", start]]}
    data, _ = budget.ask(f"aisa:refdomains-new:{rival}:{start}:{limit}", estimate(limit),
                         lambda: backend.rest(REFERRING, body), fresh, f"the new referring domains of {rival}")
    rows = [site_row(i["domain"], i.get("rank"), i.get("first_seen") or "", [rival], i.get("backlinks_spam_score"))
            for i in (data or {}).get("items") or [] if i.get("domain")]
    return rows, int((data or {}).get("total_count") or len(rows))


def linking_you(own: str, hosts: list[str], budget: Budget, fresh: bool) -> set[str]:
    """The sites among `hosts` that already link to your domain. Each host is asked as written and as its
    registrable domain, since one site can be spelled both ways across targets."""
    asked = sorted(set(hosts) | {page.registrable(h) for h in hosts})[:ROWS_MAX]
    if not asked:
        return set()
    body = {"target": own, "limit": len(asked), "backlinks_status_type": "live", "filters": [["domain", "in", asked]]}
    data, _ = budget.ask(f"aisa:refdomains-of:{own}:{','.join(asked)}", estimate(len(asked)),
                         lambda: backend.rest(REFERRING, body), fresh, f"which of them already link to {own}")
    return {page.registrable(i["domain"]) for i in (data or {}).get("items") or [] if i.get("domain")}


def shared_row(item: dict, rivals: list[str]) -> dict | None:
    """One row of the intersection ({"domain_intersection": {"1": {"target": the referring domain, ...}, ...}}), or
    None when it names fewer than two rivals."""
    found = {k: v for k, v in (item.get("domain_intersection") or {}).items()
             if v and k.isdigit() and 0 < int(k) <= len(rivals)}
    host = next((v.get("target") for v in found.values() if v.get("target")), "")
    ranks = [v["rank"] for v in found.values() if v.get("rank") is not None]
    spam = [v["backlinks_spam_score"] for v in found.values() if v.get("backlinks_spam_score") is not None]
    seen = sorted(v["first_seen"] for v in found.values() if v.get("first_seen"))
    linked = [rivals[int(k) - 1] for k in sorted(found, key=int)]
    if not host or len(linked) < 2:
        return None
    return site_row(host, max(ranks, default=None), seen[0] if seen else "", linked, max(spam, default=None))


def intersect(own: str, rivals: list[str], limit: int, budget: Budget, fresh: bool) -> tuple[list[dict], int]:
    """(the referring domains linking to two or more of the rivals and not to you; how many there are in all)."""
    body = {"targets": {str(i + 1): r for i, r in enumerate(rivals)}, "exclude_targets": [own],
            "intersection_mode": "partial", "limit": limit, "backlinks_status_type": "live"}
    data, _ = budget.ask(f"aisa:intersect:{own}:{','.join(rivals)}:{limit}", estimate(limit),
                         lambda: backend.rest(INTERSECTION, body), fresh, "the link intersect")
    rows = [r for r in (shared_row(i, rivals) for i in (data or {}).get("items") or []) if r]
    return rows, int((data or {}).get("total_count") or len(rows))


def spellings(hosts: list[str]) -> list[str]:
    """Each host and its www. form. The referring-domain lists name a site by its main domain (example.com), the
    backlinks by the host that links (www.example.com): on 2026-10-20, 6 of the 10 sites one lookup missed were
    found under www.; a site linking only from another subdomain is still missed."""
    return sorted(set(hosts) | {"www." + h for h in hosts if not h.startswith("www.")})


def examples(rival: str, hosts: list[str], budget: Budget, fresh: bool) -> dict[str, dict]:
    """{site: {"url", "title", "anchor", "followed"}}: one page of each host that links to the rival."""
    asked = spellings(hosts)
    body = {"target": rival, "mode": "one_per_domain", "limit": len(asked), "backlinks_status_type": "live",
            "filters": [["domain_from", "in", asked]]}
    data, _ = budget.ask(f"aisa:examples:{rival}:{','.join(asked)}", estimate(len(asked)),
                         lambda: backend.rest(BACKLINKS, body), fresh, f"the linking pages of {rival}")
    found: dict[str, dict] = {}
    for i in (data or {}).get("items") or []:
        found.setdefault(page.registrable(i.get("url_from") or ""), {
            "url": i.get("url_from") or "", "title": " ".join((i.get("page_from_title") or "").split()),
            "anchor": " ".join((i.get("anchor") or "").split()), "followed": i.get("dofollow")})
    found.pop("", None)
    return found


def merged(rows: list[dict]) -> list[dict]:
    """One row a site (www. and subdomains folded into it): its hosts, the rivals it links to, its best rank and the
    first day it was seen."""
    out: dict[str, dict] = {}
    for r in rows:
        m = out.setdefault(r["site"], {**r, "hosts": [], "rivals": [], "rank": None, "first_seen": "", "spam": None})
        m["hosts"] = sorted(set(m["hosts"] + r["hosts"]))
        m["rivals"] = list(dict.fromkeys(m["rivals"] + r["rivals"]))
        m["rank"] = max((x for x in (m["rank"], r["rank"]) if x is not None), default=None)
        m["first_seen"] = min((x for x in (m["first_seen"], r["first_seen"]) if x), default="")
        m["spam"] = max((x for x in (m["spam"], r["spam"]) if x is not None), default=None)
    return list(out.values())


def strongest(rows: list[dict], by_rivals: bool = False) -> list[dict]:
    """The highest rank first (with `by_rivals`, the most rivals linked before that); among equal ranks, and most
    are 0, the links that score lowest for spam."""
    return sorted(rows, key=lambda r: (-len(r["rivals"]) if by_rivals else 0, -(r["rank"] or 0), r["spam"] or 0, r["site"]))


def spammy(r: dict) -> bool:
    return (r["spam"] or 0) >= SPAM_SCORE_HIGH


def cleaned(rows: list[dict], skip: set[str], listed: dict) -> tuple[list[dict], list[dict]]:
    """(the rows kept, the rows left out): your site and the rivals go without a word; the sites on the shared
    spam-link list and the ones whose links score high for spam are left out and named."""
    rows = [r for r in rows if r["site"] not in skip]
    out = [{"site": r["site"], "why": "listed" if r["site"] in listed else f"spam score {r['spam']}"}
           for r in rows if r["site"] in listed or spammy(r)]
    gone = {o["site"] for o in out}
    return [r for r in rows if r["site"] not in gone], out


def networks(rows: list[dict]) -> list[dict]:
    """[{"kind": "template", "key", "sites"}]: NETWORK_MIN or more sites whose linking pages share one title, each
    site's own name taken out (vet.templates, which also leaves out block pages and platform defaults)."""
    pages = [{"domain": r["site"], "title": r["example"]["title"]} for r in rows if r.get("example")]
    found = {key: sorted(set(sites)) for key, sites in templates(pages).items()}
    return [{"kind": "template", "key": key, "sites": sites} for key, sites in found.items() if len(sites) >= NETWORK_MIN]


def lookups(new: dict[str, dict], shared: list[dict]) -> dict[str, list[str]]:
    """{rival: [hosts]}: the first LOOKED_UP sites of each table, each under one rival for its linking page: a new
    site under its own rival, a shared one under the first rival it links to."""
    wanted: dict[str, set[str]] = {}
    for rival, got in new.items():
        for r in got["rows"][:LOOKED_UP]:
            wanted.setdefault(rival, set()).update(r["hosts"])
    for r in shared[:LOOKED_UP]:
        wanted.setdefault(r["rivals"][0], set()).update(r["hosts"])
    return {rival: sorted(hosts) for rival, hosts in wanted.items()}


def annotate(rows: list[dict], pages: dict[str, dict]) -> None:
    """Each row's linking page, what kind of page it is and what can honestly be done there (find.kind_of)."""
    for r in rows:
        r["example"] = pages.get(r["site"])
        r["kind"] = find.kind_of(r["example"]["url"], r["example"]["title"]) if r["example"] else ""
        r["action"] = find.ACTIONS.get(r["kind"], "")


def competitors(own: str, rivals: list[str], days: int = DAYS, limit: int = LIMIT, max_usd: float = MAX_USD,
                fresh: bool = False, today: date | None = None) -> dict:
    """{"domain", "rivals", "days", "since", "new": {rival: {"rows", "total", "linking_you"}}, "shared": {"rows",
    "total"} (None with fewer than two rivals or when it was not read), "dropped": [{"site", "why"}], "networks":
    [{"kind", "key", "sites", "report"}], "cost", "max_usd", "left_out", "errors"}. A row: {"site", "hosts", "rivals",
    "rank", "first_seen", "spam", "example", "kind", "action"}."""
    own, today = page.site(own), today or date.today()
    rivals = [r for r in dict.fromkeys(page.site(x) for x in rivals) if r and r != own][:RIVALS_MAX]
    out = {"domain": own, "rivals": rivals, "days": days, "since": (today - timedelta(days=days)).isoformat(), "new": {},
           "shared": None, "dropped": [], "networks": [], "cost": 0, "max_usd": max_usd, "left_out": [], "errors": []}
    budget, limit, skip = Budget(max_usd), max(1, min(limit, ROWS_MAX)), {own, *rivals}
    listed = listed_or_none(out, fresh)
    _new(out, since(today, days), limit, budget, fresh, skip, listed or {})
    _drop_yours(out, budget, fresh)
    if len(rivals) >= 2:
        _shared(out, limit, budget, fresh, skip, listed or {})
    _examples(out, budget, fresh)
    _networks(out, listed, today)
    out.update(cost=budget.spent, left_out=budget.left_out)
    return out


def listed_or_none(out: dict, fresh: bool) -> dict | None:
    """The shared spam-link list; None, and an error, when it cannot be read: never read as empty."""
    try:
        return blocklist.load(fresh)
    except (OSError, ValueError) as exc:
        out["errors"].append(f"spam list: {exc}; listed sites were not left out")
        return None


def add_dropped(out: dict, gone: list[dict]) -> None:
    named = {d["site"] for d in out["dropped"]}
    out["dropped"] += [g for g in gone if g["site"] not in named]


def _new(out: dict, start: str, limit: int, budget: Budget, fresh: bool, skip: set[str], listed: dict) -> None:
    for rival in out["rivals"]:
        try:
            rows, total = new_domains(rival, start, limit, budget, fresh)
        except OverBudget:
            continue
        except aisa.AisaError as exc:
            out["errors"].append(f"new referring domains of {rival}: {exc}")
            continue
        kept, gone = cleaned(merged(rows), skip, listed)
        add_dropped(out, gone)
        out["new"][rival] = {"rows": strongest(kept), "total": total, "linking_you": []}


def _drop_yours(out: dict, budget: Budget, fresh: bool) -> None:
    """Takes the new sites that already link to you out of the lists, and names them."""
    hosts = [h for got in out["new"].values() for r in got["rows"] for h in r["hosts"]]
    try:
        yours = linking_you(out["domain"], hosts, budget, fresh)
    except OverBudget:
        return
    except aisa.AisaError as exc:
        out["errors"].append(f"which sites already link to {out['domain']}: {exc}")
        return
    for got in out["new"].values():
        got["linking_you"] = sorted(r["site"] for r in got["rows"] if r["site"] in yours)
        got["rows"] = [r for r in got["rows"] if r["site"] not in yours]


def _shared(out: dict, limit: int, budget: Budget, fresh: bool, skip: set[str], listed: dict) -> None:
    try:
        rows, total = intersect(out["domain"], out["rivals"], limit, budget, fresh)
    except OverBudget:
        return
    except aisa.AisaError as exc:
        out["errors"].append(f"link intersect: {exc}")
        return
    kept, gone = cleaned(merged(rows), skip, listed)
    add_dropped(out, gone)
    out["shared"] = {"rows": strongest(kept, by_rivals=True), "total": total}


def tables(out: dict) -> list[list[dict]]:
    return [got["rows"] for got in out["new"].values()] + [(out["shared"] or {}).get("rows") or []]


def _examples(out: dict, budget: Budget, fresh: bool) -> None:
    pages: dict[str, dict] = {}
    for rival, hosts in lookups(out["new"], (out["shared"] or {}).get("rows") or []).items():
        try:
            found = examples(rival, hosts, budget, fresh)
        except OverBudget:
            continue
        except aisa.AisaError as exc:
            out["errors"].append(f"linking pages of {rival}: {exc}")
            continue
        for site, example in found.items():
            pages.setdefault(site, example)
    for rows in tables(out):
        annotate(rows, pages)


def drop_networks(out: dict, tables: list[list[dict]], listed: dict | None, today: date) -> set[str]:
    """Sets out["networks"] to the networks among the rows of `tables`, each with a filled-in report for the shared
    list when it lacks REPORT_MIN or more of them (none when the list could not be read), and returns their sites
    for the caller to take out of its tables."""
    found = networks([r for rows in tables for r in rows])
    for n in found:
        unlisted = [site for site in n["sites"] if site not in (listed or {})]
        n["report"] = blocklist.report_url(n, unlisted, today) if listed is not None and len(unlisted) >= blocklist.REPORT_MIN else ""
    out["networks"] = found
    return {site for n in found for site in n["sites"]}


def _networks(out: dict, listed: dict | None, today: date) -> None:
    """Takes one network's sites out of the tables (drop_networks)."""
    members = drop_networks(out, tables(out), listed, today)
    for got in out["new"].values():
        got["rows"] = [r for r in got["rows"] if r["site"] not in members]
    if out["shared"]:
        out["shared"]["rows"] = [r for r in out["shared"]["rows"] if r["site"] not in members]
