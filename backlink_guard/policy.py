"""What each finding means, and which line of Google's spam policies it stands next to.

The clauses are the examples Google lists under "Link spam"
(https://developers.google.com/search/docs/essentials/spam-policies#link-spam, read
2026-10-13). A flag is a signal a person can check, with its evidence attached. It is
not Google's verdict: nobody outside Google can tell whether one link is counted,
ignored or held against a site.

Levels: "avoid" (a link from here is worth nothing or sits in bad company), "caution"
(look before you submit; often fine if the link is qualified), "note" (context only).
A target is avoid when any finding is avoid, caution when two or more findings are caution,
and ok otherwise: one caution finding alone is listed with its evidence but is not a verdict
(see grade). Notes never change it. An ok whose key checks failed is "incomplete" (vet.finalize).
The action reads the verdict, the link policy and the value together: what to do with the site.
"""
POLICY_URL = "https://developers.google.com/search/docs/essentials/spam-policies#link-spam"

BUYING = "Buying or selling links for ranking purposes"
EXCHANGE = "Excessive link exchanges, or requiring a link as part of an arrangement"
DIRECTORY = "Low-quality directory or bookmark site links"
AUTOMATED = "Using automated programs or services to create links to your site"
OPTIMIZED = "Links with optimized anchor text in articles, guest posts or press releases"
EXPIRED = "Expired domain abuse: an expired domain bought and used to profit from its old reputation"
HACKED = "Hacked content: content placed on a site without permission"      # the same page, outside "Link spam"
TEMPLATE = "Widely distributed links in the footers or templates of various sites"
# Not a spam policy: Google's page on redirects (read 2026-10-18), for links to pages of yours that are gone.
REDIRECTS_URL = "https://developers.google.com/search/docs/crawling-indexing/301-redirects"
MOVED = "a page that has moved for good takes a permanent server-side redirect, 301 or 308"

# id: (level, what it says, the clause it relates to or "")
FLAGS = {
    "dead": ("avoid", "The site does not load", ""),
    "parked": ("avoid", "The domain is parked or for sale", DIRECTORY),
    "deindexed": ("avoid", "Google lists no pages from this site", DIRECTORY),
    "spam_neighbors": ("avoid", "It links out to gambling, adult, loan or essay-mill sites", DIRECTORY),
    "link_farm": ("avoid", "A template page of a link network, not a site anyone reads", AUTOMATED),
    "shortener": ("avoid", "A link shortener: a link there is a redirect, not a listing", AUTOMATED),
    "link_seller": ("avoid", "Selling links is its business: PBN, DR and DA packages, guest posts", BUYING),
    "listed": ("avoid", "It is on the shared list of sites that build or sell spam backlinks, with evidence", BUYING),
    "checkout_network": ("avoid", "Its checkout link also sits on many sites built like this one (one template, or titled about link sales): one operator's network", BUYING),
    "injected_checkout": ("avoid", "It carries a checkout link for a gambling or adult product that also sits on many unrelated sites: likely injected into a hacked site", HACKED),
    "reregistered": ("caution", "Archived long before its current registration: a lapsed domain picked up again, the raw material of many link networks", EXPIRED),
    "same_template": ("caution", "Several sites in this check share one page template: likely one operator's network", AUTOMATED),
    "same_owner": ("caution", "It reports to the same analytics or ads account as other sites in this check: one operator's sites", AUTOMATED),
    "traffic_cliff": ("caution", "Its visits fell sharply within a month and have not come back", DIRECTORY),
    "scaled_pages": ("caution", "Thousands of pages listed, almost none ranking: the shape of scaled, low-value content", DIRECTORY),
    "search_fall": ("caution", "It lost most of its Google search traffic in the last year and has not won it back", DIRECTORY),
    "hollow_rating": ("caution", "A high rating with almost no visitors: the rating comes from links, not readers", EXCHANGE),
    "paid_follow": ("caution", "It sells links or posts that pass ranking credit", BUYING),
    "link_exchange": ("caution", "It asks for a link or badge back as a condition", EXCHANGE),
    "spam_score": ("caution", "Its own backlink profile scores high for spam", DIRECTORY),
    "badge_network": ("caution", "Its rating comes from badges its listed sites must show: sitewide footer links", EXCHANGE),
    "unproven": ("caution", "New, almost nobody links to it, almost nobody visits: Ahrefs marks most such sites spam", DIRECTORY),
    "not_indexing": ("caution", "It keeps adding pages, but Google shows none of them from the last 30 days", DIRECTORY),
    "inactive": ("note", "No new page in the last 30 days, by its own sitemap and by Google", ""),
    "no_audience": ("note", "Almost nobody visits it", ""),
    "traffic_decline": ("note", "Its visits are less than half of their level earlier in the year", ""),
    "traffic_drop": ("note", "Its visits fell sharply in the newest month of the data; the next month shows whether the fall holds", ""),
    "old_search_fall": ("note", "It lost most of its Google search traffic over a year ago and has not won it back", ""),
    "paid_listing": ("note", "It charges for a listing or for faster review", ""),
    "guest_posts": ("note", "Google holds pages of it that invite guest or sponsored posts", ""),
    "young": ("note", "The domain first appeared less than a year ago", ""),
    "blocked": ("note", "The site refused the check; the page signals are missing", ""),
    # your own profile
    "velocity_spike": ("caution", "New referring domains jumped well above your usual week", AUTOMATED),
    "anchor_repeat": ("caution", "One keyword anchor makes up a large share of your links", OPTIMIZED),
    "spammy_referrers": ("caution", "Several of your top linking sites score high for spam", DIRECTORY),
    "spam_anchor": ("caution", "Links to you carry anchors that sell links or name gambling, adult or loan sites", BUYING),
    "pace": ("caution", "More submissions this week than your own limit", AUTOMATED),
    "few_followed": ("note", "Very few of your links pass ranking credit", ""),
    "sitewide": ("note", "Some sites link to you from many of their pages (site-wide): each counts as one source", TEMPLATE),
    "dead_target": ("note", "Sites link to pages of yours that no longer exist: the links reach nothing", MOVED),
}
# Findings that are a link-spam behaviour of the site itself (selling links, asking for them back, a network, an
# expired domain picked up, a hacked page), with the short label a report column uses. The other findings say how
# healthy the site is. A verdict weighs both; the policy column shows these on their own, even one.
POLICY = {
    "link_seller": "sells links as its business", "checkout_network": "its checkout link sits on a network",
    "injected_checkout": "hacked: an injected checkout link", "link_farm": "a link network's template page",
    "shortener": "a URL shortener", "spam_neighbors": "links out to gambling, adult or loan sites",
    "paid_follow": "sells followed links", "link_exchange": "asks for a link back", "badge_network": "a badge network",
    "same_template": "one template with others here", "same_owner": "one owner with others here",
    "reregistered": "an expired domain picked up again", "listed": "on the shared spam-link list",
}
# A link there brings nobody and passes nothing: the value column says "none".
NO_VALUE = {"dead", "parked", "deindexed", "link_farm", "shortener"}
# For the action: policy findings that say one operator may run several such sites (look before you submit), and
# the ones that say what the site asks for, which a free listing does not need.
NETWORK = {"same_template", "same_owner", "reregistered"}
DEALS = {"paid_follow": "never pay for a followed link", "link_exchange": "never link back as a condition",
         "badge_network": "never show its badge in your footer"}
ACTIONS = ("skip", "look first", "free only", "low value", "submit")
ORDER = {"avoid": 0, "caution": 1, "note": 2}
RISK = {"avoid": 3, "caution": 1, "note": 0}
CAUTION_MIN = 2                 # caution findings it takes to make a caution: one alone is shown, not a verdict


def flag(name: str, evidence: str) -> dict:
    level, meaning, clause = FLAGS[name]
    return {"flag": name, "level": level, "meaning": meaning, "evidence": evidence, "policy": clause}


def grade(flags: list[dict]) -> str:
    """avoid when any finding is avoid; caution when CAUTION_MIN or more are caution; else ok.
    Chosen on 100 sites no rule had been tuned on (2026-10-16: two sites' referring domains with Ahrefs' SPAM mark,
    link networks left out): one caution as a verdict flagged 43 of 60 normal sites; two, with the spam score counted
    from 50, flag 21 and still catch 28 of 40 SPAM. The 12 let through had one weak finding at most, 11 of them under
    1,500 visits a month."""
    levels = [f["level"] for f in flags]
    return "avoid" if "avoid" in levels else "caution" if levels.count("caution") >= CAUTION_MIN else "ok"


def risk(flags: list[dict]) -> int:
    """3 for each avoid finding and 1 for each caution, notes 0: of two sites with one verdict, the one
    with more found against it. On 90 sites Ahrefs had labelled, 33 of them SPAM (2026-10-15), it put a
    SPAM site above a normal one 76% of the time; the verdict alone did 62%."""
    return sum(RISK[f["level"]] for f in flags)


def policy_risk(flags: list[dict]) -> str:
    """"avoid", "caution" or "clean": the worst policy finding, one being enough."""
    levels = {f["level"] for f in flags if f["flag"] in POLICY}
    return "avoid" if "avoid" in levels else "caution" if "caution" in levels else "clean"


def value(flags: list[dict], reach: str) -> str:
    """What a listing there can bring: "none" when nobody can reach it, else the reach ("high", "medium",
    "low", or "" when visits are unknown). On two sites' analytics (2026-10-16) reach told apart the referring
    domains that sent visitors: 10 of 14 rated high had, 2 of 37 rated low; on the other, 2 of 7 and 1 of 73."""
    return "none" if any(f["flag"] in NO_VALUE for f in flags) else reach


def action(r: dict) -> tuple[str, str]:
    """(one of ACTIONS, why): the verdict, link policy and value of a graded row read together, first rule first.
    Low reach weighs because it predicts what a listing brings: on two sites' analytics (2026-10-16) 2 of the 37
    and 1 of the 73 referring domains rated low had sent a visit, against 10 of 14 and 2 of 7 rated high."""
    found = [f for f in r["flags"] if f["level"] != "note"]
    if r["grade"] == "avoid":
        return "skip", next(f["meaning"] for f in found if f["level"] == "avoid")
    if r["value"] == "none":
        return "skip", "nobody can reach it"
    if r["grade"] == "caution" and r["value"] == "low":
        return "skip", "findings against it, and almost nobody visits"
    if r["grade"] == "incomplete":
        return "look first", "a check failed: run it again"
    if any(f["flag"] == "blocked" for f in r["flags"]):
        return "look first", "it refused the check, so its pages were not read"
    network = [POLICY[f["flag"]] for f in found if f["flag"] in NETWORK]
    if network:
        return "look first", "; ".join(network)
    deals = [DEALS[f["flag"]] for f in found if f["flag"] in DEALS]
    if deals:
        return "free only", "; ".join(deals)
    if r["grade"] == "caution":
        return "look first", "two findings against it"
    if not r["value"]:
        return "look first", "visits not checked"
    if r["value"] == "low":
        return "low value", "under 1,000 visits a month: a listing there brings few visitors"
    return "submit", ""


def ranked(flags: list[dict]) -> list[dict]:
    return sorted(flags, key=lambda f: ORDER[f["level"]])
