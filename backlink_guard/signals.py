"""Signals added in 0.5, after a 56-tool list for selling software abroad (2026-10-14).

- From the GoAnyAPI visits answer the check already pays for: when the domain was registered,
  where its visitors come from (search, direct, social, referrals, AI assistants) and how they
  behave. No extra call.
- Re-registered domains: archived years before its current registration date means the domain
  lapsed and someone picked it up again, the usual raw material of a link network (Google's
  spam policies call the abuse of it "expired domain abuse").
- Guest-post pages: a Google search for the site's own "write for us" or "sponsored post"
  pages (GoAnyAPI, 2 credits), found even when the home page does not link to them.
- Entity: whether Google's Knowledge Graph knows the site and as what ("Website", "Company",
  "AI agent"), from Google Trends' suggestions (free). Real publications and brands are
  entities; link networks rarely are.
- With --deep, three more (Ahrefs and others through AIsa; they draw on AIsa's media
  credits while an account has them): Ahrefs' Domain Rating as a second rating ($0.08), the
  site's technology ($0.012), and how often ChatGPT's answers mention it ($0.10). Semrush's
  organic keywords and traffic come from AIsa's pay-as-you-go balance ($0.001).
"""
from __future__ import annotations

import csv
import io
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from . import UA, aisa, goanyapi
from .policy import flag

REREGISTERED_GAP = 365          # days between the first archived copy and the current registration
REREGISTERED_RECENT = 3 * 365   # ... and that registration this recent: Product Hunt's (2003) and There's An
                                # AI For That's (2022) are businesses built on bought domains, not pick-ups
REREGISTERED_VISITS = 100_000   # a site this busy has readers, whatever the domain's past
POLICY_PAGE = re.compile(r"write[\s_-]?for[\s_-]?us|guest[\s_-]?post(?:ing)?[\s_-]?guidelines|submit[\s_-]a[\s_-]guest[\s_-]post|"
                         r"become[\s_-]a[\s_-]contributor|contribute[\s_-]?(?:to[\s_-]us)?$|sponsored[\s_-]posts?[\s_-](?:pricing|rates)", re.I)
GUEST = '("write for us" OR "guest post" OR "sponsored post" OR "submit a guest post")'
TRENDS = "https://trends.google.com/trends/api/autocomplete/{}?hl=en-US&tz=0"
TRENDS_TIMEOUT = 20
AHREFS_TOOL = "get_ahrefs_domain_rating"
TECH_TOOL = "post_dataforseo_domains_tech_for_domain_live"
MENTIONS_TOOL = "post_dataforseo_ai_llm_mentions_aggregated_metrics_live"
SEMRUSH_TOOL = "get_semrush_domain_overview"
SOURCES = {"Direct": "direct", "Search": "search", "SearchPaid": "search", "Social": "social", "SocialPaid": "social",
           "Referrals": "referrals", "Affiliate": "referrals", "Mail": "mail", "DisplayAds": "ads", "GenAI": "ai"}


def audience(data: dict) -> dict:
    """registered, sources {kind: share}, top_source, ai_share and engagement, from a GoAnyAPI visits answer."""
    out: dict = {}
    registered = str(((data.get("DateData") or {}).get("registration")) or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", registered):
        out["registered"] = registered
    shares: dict[str, float] = {}
    for key, value in (data.get("TrafficSources") or {}).items():
        try:
            shares[SOURCES.get(key, "other")] = shares.get(SOURCES.get(key, "other"), 0.0) + float(value or 0)
        except (TypeError, ValueError):
            continue
    if sum(shares.values()) > 0:
        out["sources"] = {k: round(v, 3) for k, v in sorted(shares.items(), key=lambda kv: -kv[1])}
        out["top_source"] = next(iter(out["sources"]))
        out["ai_share"] = out["sources"].get("ai", 0.0)
    month = next((v for v in data.values() if isinstance(v, dict) and "BounceRate" in v), None)
    if month:
        try:
            out["bounce"] = round(float(month["BounceRate"]), 2)
            out["pages_per_visit"] = round(float(month["PagePerVisit"]), 2)
        except (KeyError, TypeError, ValueError):
            pass
    return out


def reregistered(first_archived: str, registered: str, today: date, visits: int | None) -> dict | None:
    """A flag when the site was archived long before a recent registration and few people visit it."""
    if not first_archived or not registered or (visits or 0) >= REREGISTERED_VISITS:
        return None
    reg = datetime.strptime(registered, "%Y-%m-%d").date()
    gap = (reg - datetime.strptime(first_archived, "%Y-%m-%d").date()).days
    if gap < REREGISTERED_GAP or (today - reg).days > REREGISTERED_RECENT:
        return None
    return flag("reregistered", f"first archived {first_archived}, registered again {registered}")


def guest_posts(domain: str, ask) -> tuple[dict | None, int]:
    """(a note flag when Google holds pages of the site that ask for guest or sponsored posts, cost).
    `ask(question, fn)` is vet.paid bound to the cache."""
    data, cost = ask(f"guest:{domain}", lambda: goanyapi.call("serp", q=f"site:{domain} {GUEST}", gl="US", hl="en"))
    hits = [o for o in (data.get("result") or {}).get("organic") or [] if domain in (o.get("link") or "")
            and (POLICY_PAGE.search(urllib.parse.urlsplit(o.get("link") or "").path.strip("/").split("/")[-1])
                 or POLICY_PAGE.search((o.get("title") or "").split(" - ")[0].split(" | ")[0]))]   # its own page, not a listing
    if not hits:
        return None, cost
    return flag("guest_posts", f"{len(hits)} such page(s), e.g. {hits[0].get('link')}"), cost


def _plain(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def entity_of(raw: str, domain: str) -> str:
    """The type of the suggestion whose title is the site's name, from a Trends answer (")]}'," then JSON)."""
    brand = domain.split(".")[0]
    names = {_plain(domain), _plain(brand)}
    try:
        topics = json.loads(raw[raw.index("{"):]).get("default", {}).get("topics", [])
    except ValueError:
        return ""
    return next((t.get("type") or "" for t in topics if _plain(t.get("title") or "") in names), "")


def entity(domain: str) -> str:
    """Google's Knowledge Graph type for the site ("Website", "Topic", "AI agent"), "" when it has none."""
    for query in (domain, domain.split(".")[0]):
        try:
            url = TRENDS.format(urllib.parse.quote(query))
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=TRENDS_TIMEOUT) as res:
                found = entity_of(res.read().decode("utf-8", "replace"), domain)
        except OSError:
            return ""
        if found:
            return found
    return ""


def semrush(domain: str) -> tuple[dict, int]:
    """US organic keywords and traffic by Semrush ({} when it has no row)."""
    data, cost = aisa.tool(SEMRUSH_TOOL, {"domain": domain, "database": "us"})
    rows = list(csv.DictReader(io.StringIO(data if isinstance(data, str) else ""), delimiter=";"))
    if not rows:
        return {}, cost
    to_int = lambda v: int(float(v)) if str(v).replace(".", "", 1).isdigit() else None  # noqa: E731
    return {"semrush_keywords": to_int(rows[0].get("Organic Keywords")), "semrush_traffic": to_int(rows[0].get("Organic Traffic"))}, cost


def deep(domain: str, today: date, ask) -> tuple[dict, int, list[str]]:
    """Ahrefs' rating, the site's technology, ChatGPT mentions and Semrush's organic numbers.
    `ask(question, fn)` is vet.paid bound to the cache: each is bought once."""
    metrics, cost, errors = {}, 0, []
    steps = [
        ("ahrefs", lambda: aisa.tool(AHREFS_TOOL, {"target": domain, "date": (today - timedelta(days=1)).isoformat()}),
         lambda d: {"ahrefs_dr": ((d or {}).get("domain_rating") or {}).get("domain_rating")}),
        ("technology", lambda: aisa.call(TECH_TOOL, {"target": domain}),
         lambda d: {"tech": sorted({name for group in ((d or {}).get("technologies") or {}).values()
                                    for names in (group or {}).values() for name in names or []})}),
        ("AI mentions", lambda: aisa.call(MENTIONS_TOOL, {"target": [{"domain": domain}], "platform": "chat_gpt",
                                                          "location_code": 2840, "language_code": "en"}),
         lambda d: {"ai_mentions": sum(int(x.get("mentions") or 0) for x in (((d or {}).get("total") or {}).get("platform") or []))}),
    ]
    for name, fetch, read in steps:
        try:
            data, spent = ask(f"{name}:{domain}", fetch)
            metrics.update(read(data))
            cost += spent
        except aisa.AisaError as exc:
            if "no result" in str(exc).lower():     # AIsa knows nothing of the site: zero, not a failure
                metrics.update(read({}))
            else:
                errors.append(f"{name}: {exc}")
    try:
        more, spent = ask(f"semrush:{domain}", lambda: semrush(domain))
        metrics.update(more)
        cost += spent
    except aisa.AisaError as exc:
        errors.append(f"semrush: {exc}")
    return metrics, cost, errors
