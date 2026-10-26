"""Checkout links shared across sites (0.5, from the payment-link history of 2026-10-15).

A checkout link (a Stripe Payment Link, a Gumroad product, Lemon Squeezy, Polar, Creem, Dodo or
Paddle) belongs to one seller. When the one a site carries also sits on many other sites, either
one operator's network sells through it or it was injected into hacked sites. On 2026-10-15 one
Stripe link sat on 395 sites titled like "Backlink Generator Tool" and "SEO Score Checker", and a
Gumroad link for an escort service had been injected into 262 schools, clinics and museums. A
product people write about is shared too (MacWhisper's link sat on 705 sites), by sites that look
nothing alike: that is not flagged.

Network sites put their checkout links on a few of thousands of inner pages (/dir/<slug>-<id>),
which no sample of pages finds (six sitemap pages of two network sites held none). So the home page
is read for free, and with --deep Glasser or AIsa also lists the site's links to Stripe and Gumroad, the
platforms of nearly every shared link (one call each, about $0.024). One more call per checkout link
found (about $0.02), at most LOOKED_AT per site; most link sources carry none and cost little.
"""
from __future__ import annotations

import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from . import aisa, backend, page
from .policy import flag

TOOL = "post_dataforseo_backlinks_backlinks_live"
CHECKOUT = re.compile(r"https?://(?:buy\.stripe\.com/[A-Za-z0-9_]+|(?:[a-z0-9-]+\.)?gumroad\.com/l/[^/?#\s]+|"
                      r"[a-z0-9-]+\.lemonsqueezy\.com/(?:checkout/)?buy/[^/?#\s]+|buy\.polar\.sh/[^/?#\s]+|"
                      r"(?:www\.)?creem\.io/payment/[^/?#\s]+|checkout\.dodopayments\.com/buy/[^/?#\s]+|"
                      r"buy\.paddle\.com/[^?#\s]+)", re.I)
LOOKED_AT = 2           # checkout links looked up per site
LIMIT = 100             # other sites read per checkout link
SHARED_MIN = 5          # other sites carrying the same link before it means anything
TEMPLATE_SHARE = 0.4    # this share of those sites' titles alike (same ending, or about selling links)
TAIL_WORDS = 2          # "drjack.world | Keyword Rankingss": the site's name sits right before the template's words
TITLES_READ = 24        # the backlink rows leave most page titles empty: this many home pages are read for theirs
MIRRORS_MAX = 20        # up to this many sites with one identical title can be one site on several domains (17 seen)
INJECTED_RELATED = 0.3  # a gambling or adult product cited by sites on its own topic is promotion, not injection
PLATFORMS = ("stripe.com", "gumroad.com")     # with --deep: where the site's own checkout links are looked for
LINKED = 20             # of the site's links to each
# What the network sites of 2026-10-15 were titled: SEO tools and link sales, one template per site.
LINK_TRADE = re.compile(r"\bbacklinks?\b|\blink building\b|\bguest posts?\b|\bkeyword ranking|\bchecker\b|\bpbn\b|"
                        r"\b(?:traffic|backlink) generator\b|\bda\s*pa\b|\baged domains?\b|\bdomain authority\b", re.I)   # not "seo": SEO blogs cite SEO courses
# Words of the products injected into hacked sites, besides the gambling and adult words vet already has.
INJECTED = re.compile(r"\b(?:travesti|bahis|bokep|jav|call ?girls?|escorts?)\b", re.I)


def links_on(links: list[dict]) -> list[str]:
    """The checkout links among `links`, query strings dropped, the first LOOKED_AT in page order."""
    found: list[str] = []
    for link in links:
        m = CHECKOUT.match(link["href"])
        url = m.group(0).rstrip("/") if m else ""
        if url and url not in found:
            found.append(url)
    return found[:LOOKED_AT]


def linked(site: str, ask) -> tuple[list[dict], int]:
    """With --deep: the site's links to PLATFORMS, as page links ({"href"}), and the cost."""
    found, cost = [], 0
    for target in PLATFORMS:
        data, spent = ask(f"checkout-from:{site}:{target}", lambda target=target: backend.rest("backlinks/backlinks/live", {
            "target": target, "mode": "as_is", "limit": LINKED, "backlinks_status_type": "live",
            "filters": [["domain_from", "like", f"%{site}"]]}))
        found += [{"href": i.get("url_to") or ""} for i in (data or {}).get("items") or []]
        cost += spent
    return found, cost


def others(url: str, own: str, ask) -> tuple[list[dict], int]:
    """The other sites linking to `url`: [{"site", "title"}] (one row a site), and the cost."""
    try:
        data, cost = ask(f"checkout:{url}", lambda: backend.call(TOOL, {
            "target": url, "mode": "one_per_domain", "limit": LIMIT, "backlinks_status_type": "live"}))
    except aisa.AisaError as exc:
        if "no result" in str(exc).lower():         # nobody links to it: nothing shared
            return [], 0
        raise
    rows, seen = [], {own}
    for item in (data or {}).get("items") or []:
        site = page.site("https://" + (item.get("domain_from") or ""))
        if site and site not in seen:
            seen.add(site)
            rows.append({"site": site, "title": item.get("page_from_title") or "", "host": item.get("domain_from") or site})
    return titled(rows), cost


def titled(rows: list[dict]) -> list[dict]:
    """Rows with a title: the ones the backlink rows left empty read from their home pages, TITLES_READ at most."""
    blank = [r for r in rows if not r["title"].strip()][:TITLES_READ]
    with ThreadPoolExecutor(12) as pool:
        for r, got in zip(blank, pool.map(lambda r: page.fetch(f"https://{r['host']}/"), blank)):
            r["title"] = page.parse(got["html"], got["final"])["title"] if got["html"] else ""
    return rows


def tail(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return " ".join(words[-TAIL_WORDS:]) if len(words) > TAIL_WORDS else ""


def judge(url: str, own_title: str, rows: list[dict], spam: re.Pattern) -> dict | None:
    """A flag when the site is one of many carrying `url` and is like them: titled about link sales, or built
    from the same template, or one of the unrelated sites a spam product was injected into. A site whose
    link was merely copied onto such sites (the seller's own, or one that cites the product) is not flagged.
    Counted by site: on 2026-10-15, 94-99 of the 100 sites carrying each of three network links shared one
    title ("Expert backlink building services for higher Google rankings..."). A few sites with one identical
    title are more likely one site on several domains, which a template needs more of (MIRRORS_MAX) to count."""
    n = len(rows)
    if n < SHARED_MIN:
        return None
    count = f"{n}{'+' if n >= LIMIT else ''}"
    examples = ", ".join(r["site"] for r in rows[:3])
    own = " ".join(own_title.lower().split())
    titles = [" ".join(r["title"].lower().split()) for r in rows if r["title"].strip()]
    need = max(SHARED_MIN, TEMPLATE_SHARE * len(titles))
    if spam.search(url) or INJECTED.search(url):
        related = sum(1 for t in titles if spam.search(t) or INJECTED.search(t))
        if related < INJECTED_RELATED * len(titles) and not (spam.search(own) or INJECTED.search(own)):
            return flag("injected_checkout", f"{url} also sits on {count} other unrelated sites, e.g. {examples}")
        return None
    trade = sum(1 for t in titles if LINK_TRADE.search(t))
    if trade >= need and LINK_TRADE.search(own) and len(set(titles)) > 1 or trade >= max(need, MIRRORS_MAX + 1) and LINK_TRADE.search(own):
        return flag("checkout_network", f"{url} also sits on {count} other sites; {trade} of them are titled about "
                                        f"backlinks, link checkers or link sales, like this one, e.g. {examples}")
    by_tail: dict[str, list[str]] = {}
    for t in titles:
        if tail(t):
            by_tail.setdefault(tail(t), []).append(t)
    ending, group = max(by_tail.items(), key=lambda kv: len(kv[1]), default=("", []))
    template = len(set(group)) >= 3 or len(group) > MIRRORS_MAX
    if len(group) >= need and template and tail(own) == ending:
        return flag("checkout_network", f"{url} also sits on {count} other sites; {len(group)} of their titles end "
                                        f"\"…{ending}\" like this one's, e.g. {examples}")
    return None


def shared(read: dict, own: str, ask, spam: re.Pattern, deep: bool = False) -> tuple[list[dict], int, list[str]]:
    """(flags, cost, errors) for the checkout links on a site read by vet.read_site; with `deep`, also the ones
    the backlink index saw on its other pages."""
    flags, cost, errors = [], 0, []
    links = list(read["parsed"]["links"])
    if deep:
        try:
            more, cost = linked(own, ask)
            links += more
        except aisa.AisaError as exc:
            errors.append(f"checkout links: {exc}")
    for url in links_on(links):
        try:
            rows, spent = others(url, own, ask)
        except aisa.AisaError as exc:
            errors.append(f"checkout link {url}: {exc}")
            continue
        cost += spent
        found = judge(url, read["parsed"]["title"], rows, spam)
        if found and found["flag"] not in {f["flag"] for f in flags}:        # one flag of a kind, the first link's evidence
            flags.append(found)
    return flags, cost, errors
