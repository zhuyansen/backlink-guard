"""What each finding means, and which line of Google's spam policies it stands next to.

The clauses are the examples Google lists under "Link spam"
(https://developers.google.com/search/docs/essentials/spam-policies#link-spam, read
2026-10-13). A flag is a signal a person can check, with its evidence attached. It is
not Google's verdict: nobody outside Google can tell whether one link is counted,
ignored or held against a site.

Levels: "avoid" (a link from here is worth nothing or sits in bad company), "caution"
(look before you submit; often fine if the link is qualified), "note" (context only).
The grade of a target is its worst level; notes never change it.
"""
POLICY_URL = "https://developers.google.com/search/docs/essentials/spam-policies#link-spam"

BUYING = "Buying or selling links for ranking purposes"
EXCHANGE = "Excessive link exchanges, or requiring a link as part of an arrangement"
DIRECTORY = "Low-quality directory or bookmark site links"
AUTOMATED = "Using automated programs or services to create links to your site"
OPTIMIZED = "Links with optimized anchor text in articles, guest posts or press releases"

# id: (level, what it says, the clause it relates to or "")
FLAGS = {
    "dead": ("avoid", "The site does not load", ""),
    "parked": ("avoid", "The domain is parked or for sale", DIRECTORY),
    "deindexed": ("avoid", "Google lists no pages from this site", DIRECTORY),
    "spam_neighbors": ("avoid", "It links out to gambling, adult, loan or essay-mill sites", DIRECTORY),
    "traffic_cliff": ("caution", "Its visits fell sharply within a month and have not come back", DIRECTORY),
    "hollow_rating": ("caution", "A high rating with almost no visitors: the rating comes from links, not readers", EXCHANGE),
    "paid_follow": ("caution", "It sells links or posts that pass ranking credit", BUYING),
    "link_exchange": ("caution", "It asks for a link or badge back as a condition", EXCHANGE),
    "spam_score": ("caution", "Its own backlink profile scores high for spam", DIRECTORY),
    "no_audience": ("note", "Almost nobody visits it", ""),
    "traffic_decline": ("note", "Its visits are less than half of their level earlier in the year", ""),
    "paid_listing": ("note", "It charges for a listing or for faster review", ""),
    "young": ("note", "The domain first appeared less than a year ago", ""),
    "blocked": ("note", "The site refused the check; the page signals are missing", ""),
    # your own profile
    "velocity_spike": ("caution", "New referring domains jumped well above your usual week", AUTOMATED),
    "anchor_repeat": ("caution", "One keyword anchor makes up a large share of your links", OPTIMIZED),
    "spammy_referrers": ("caution", "Several of your top linking sites score high for spam", DIRECTORY),
    "spam_anchor": ("caution", "Links to you carry anchors that sell links or name gambling, adult or loan sites", BUYING),
    "pace": ("caution", "More submissions this week than your own limit", AUTOMATED),
    "few_followed": ("note", "Very few of your links pass ranking credit", ""),
}
ORDER = {"avoid": 0, "caution": 1, "note": 2}


def flag(name: str, evidence: str) -> dict:
    level, meaning, clause = FLAGS[name]
    return {"flag": name, "level": level, "meaning": meaning, "evidence": evidence, "policy": clause}


def grade(flags: list[dict]) -> str:
    levels = {f["level"] for f in flags}
    return "avoid" if "avoid" in levels else "caution" if "caution" in levels else "ok"


def ranked(flags: list[dict]) -> list[dict]:
    return sorted(flags, key=lambda f: ORDER[f["level"]])
