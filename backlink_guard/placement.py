"""Where on a page a link sits.

An editor's link inside the body text of an article is a different thing from a link
in a navigation bar, a sidebar widget, a footer, a comment or an author box. Google
names "widely distributed links in the footers or templates of various sites" and
links "embedded in widgets" in its examples of link spam, and the people who build
links for a living rank body-text links far above the rest.

The page's own HTML says where a link is: the elements around it (article, main, nav,
aside, footer) and their class and id names (sidebar, widget, comment, author). This
reads them from the inside out; the first one that names a region decides.
"""
from __future__ import annotations

import re

TEXT_TAGS = {"p", "li", "blockquote", "td", "dd", "figcaption"}
# Checked in this order on each element, innermost element first.
REGIONS = (
    ("comments", (), (), {"comment", "comments", "disqus", "reply", "replies"}),
    ("author box", (), (), {"author", "authorbox", "byline", "bio", "signature"}),
    ("footer", ("footer",), ("contentinfo",), {"footer"}),
    ("sidebar", ("aside",), ("complementary",), {"sidebar", "widget", "widgets"}),
    ("navigation", ("nav",), ("navigation",), {"nav", "navbar", "menu", "breadcrumb", "breadcrumbs", "pagination"}),
    ("header", ("header",), ("banner",), set()),
    ("content", ("article", "main"), ("main", "article"), {"content", "post", "entry", "article", "prose", "markdown"}),
)
LABELS = ("body text", "main area", "header", "navigation", "sidebar", "footer", "comments", "author box", "unknown")
IN_TEXT = {"body text"}


def tokens(attrs: str) -> set[str]:
    """"site-footer widget_text" -> {"site", "footer", "widget", "text", "site-footer", "widget_text"}"""
    words = set(attrs.split())
    return words | {part for w in words for part in re.split(r"[-_]+", w) if part}


def region(tag: str, attrs: str, role: str) -> str:
    names = tokens(attrs)
    for name, tags, roles, words in REGIONS:
        if tag in tags or role in roles or names & words:
            return name
    return ""


def where(ancestors: list[tuple[str, str, str]]) -> str:
    """ancestors: (tag, "class and id", role) from the outermost element to the link's parent."""
    in_text = any(tag in TEXT_TAGS for tag, _, _ in ancestors)
    for tag, attrs, role in reversed(ancestors):
        found = region(tag, attrs, role)
        if found == "content":
            return "body text" if in_text else "main area"
        if found:
            return found
    return "body text" if in_text else "unknown"
