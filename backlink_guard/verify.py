"""After a site says it listed you: is the link there, and does it pass ranking credit?

Reads the page's HTML as served. A link a script adds later is not seen, and the result
says so instead of calling the listing missing. What counts, from checking five guest
posts and several directories by hand in July 2026: only rel="nofollow", "sponsored" or
"ugc" hold back credit ("noopener" and "external" do not), and a link routed through the
site's own redirect page (/go/?url=...) does not reach you directly.
"""
from __future__ import annotations

import base64
import binascii
import re
import urllib.parse

from . import page

QUALIFIED = {"nofollow", "sponsored", "ugc"}
TOKEN = re.compile(r"[A-Za-z0-9+/_\-]{16,}={0,2}")


def _decoded(href: str) -> str:
    """The href with any base64 parts decoded, so an encoded redirect target can be seen."""
    found = []
    for token in TOKEN.findall(href):
        padded = token + "=" * (-len(token) % 4)
        try:
            found.append(base64.urlsafe_b64decode(padded).decode("utf-8", "ignore"))
        except (binascii.Error, ValueError):
            continue
    return urllib.parse.unquote(href) + " " + " ".join(found)


def classify(link: dict, domain: str, own: str) -> dict | None:
    """How one link on the page relates to `domain`, or None when it does not."""
    href = link["href"]
    if page.site(href) == domain:
        how = "direct"
    elif page.site(href) == own and domain in _decoded(href).lower():
        how = "redirect"
    else:
        return None
    held = sorted(link["rel"] & QUALIFIED)
    return {"href": href, "anchor": link["text"][:120], "rel": sorted(link["rel"]), "how": how,
            "passes_credit": how == "direct" and not held, "insecure": href.startswith("http://")}


def verify(page_url: str, domain: str) -> dict:
    """{"page", "domain", "status", "links": [...], "verdict", "note"}"""
    domain, got = page.site(domain), page.fetch(page_url)
    out = {"page": page_url, "domain": domain, "status": got["status"], "links": [], "verdict": "", "note": ""}
    if got["dead"] or got["blocked"]:
        out.update(verdict="unreadable", note=f"The page could not be read ({got['error']}). Open it in a browser to check.")
        return out
    parsed = page.parse(got["html"], got["final"])
    out["links"] = [c for c in (classify(l, domain, page.site(got["final"])) for l in parsed["links"]) if c]
    if not out["links"]:
        mentioned = domain in got["html"].lower()
        out.update(verdict="not found", note="The domain appears in the page source but not as a link: a script may add it."
                   if mentioned else "No link to the domain in the page as served.")
    elif any(l["passes_credit"] for l in out["links"]):
        out["verdict"] = "followed link"
    elif any(l["how"] == "direct" for l in out["links"]):
        out.update(verdict="qualified link", note="The link is there with rel=nofollow, sponsored or ugc: visitors, no ranking credit.")
    else:
        out.update(verdict="redirect only", note="The link goes through the site's own redirect: visitors, no ranking credit.")
    return out
