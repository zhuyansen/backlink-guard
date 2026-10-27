"""Read a web page the way the checks need it: status, where it ended up, its links
with their rel values, and its visible text. Standard library only.

A site that answers with an HTTP error other than 404 or 410 has refused the request
(dev.to answers 406 to an unknown client), which says nothing about the site: `blocked`
is reported apart from `dead`.
"""
from __future__ import annotations

import http.client
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from . import UA, placement

TIMEOUT = 20
MAX_BYTES = 1_500_000
GONE = {404, 410}             # any other HTTP error means the request was refused, not that the site is gone
REDIRECTS = {301, 302, 303, 307, 308}
MAX_HOPS = 10                 # Googlebot follows up to 10 redirect hops (Google's page on site moves)
# Two-label public suffixes common among the sites people submit to; enough to tell
# "blog.example.co.uk" from "example.co.uk" without a suffix list.
TWO_LABEL_SUFFIXES = {"co.uk", "com.au", "com.br", "co.jp", "com.cn", "co.in", "com.tr", "co.kr", "com.mx", "co.nz",
                      "org.uk", "ac.uk", "net.au", "org.au", "com.sg", "com.hk", "com.tw", "co.za", "com.ar", "co.id",
                      # 0.8: a shop on .com.co came out as the site "com.co" among a competitor's referring domains
                      "com.co", "com.vn", "com.ua", "com.my", "com.ph", "com.pk", "com.ng", "co.th", "co.il", "com.pe",
                      "net.cn", "org.cn", "ne.jp", "or.jp"}
# Hosts where each subdomain is somebody else's site: when links are counted by referring domain,
# alice.github.io and bob.github.io are two (page.registrable). vet keeps reading them as one platform.
HOSTED = {"github.io", "blogspot.com", "wordpress.com", "netlify.app", "vercel.app", "pages.dev", "substack.com",
          "tumblr.com", "web.app", "gitbook.io", "notion.site", "herokuapp.com"}
SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
# A <p> ends where one of these starts, even when the page never closes it.
CLOSES_P = {"address", "article", "aside", "blockquote", "div", "dl", "fieldset", "footer", "form", "h1", "h2", "h3",
            "h4", "h5", "h6", "header", "hr", "main", "nav", "ol", "p", "pre", "section", "table", "ul"}


def host(url: str) -> str:
    netloc = urllib.parse.urlsplit(url if "//" in url else "//" + url).netloc.lower()
    return netloc.split("@")[-1].split(":")[0].removeprefix("www.")


def site(url: str) -> str:
    """The registrable domain: blog.example.com and example.com are one site."""
    labels = host(url).split(".")
    keep = 3 if ".".join(labels[-2:]) in TWO_LABEL_SUFFIXES else 2
    return ".".join(labels[-keep:])


def registrable(url: str) -> str:
    """site(), except that a subdomain of a shared host (HOSTED) is its own site: the referring domain of a link."""
    name = host(url)
    hosted = next((h for h in HOSTED if name.endswith("." + h)), "")
    return ".".join(name.split(".")[-(hosted.count(".") + 2):]) if hosted else site(url)


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict] = []
        self.text: list[str] = []
        self.title = ""
        self._skip = 0
        self._open: dict | None = None
        self._in_title = False
        self._stack: list[tuple[str, str, str]] = []      # open elements: (tag, "class id", role)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag == "a" and a.get("href"):
            self._open = {"href": a["href"].strip(), "rel": set((a.get("rel") or "").lower().split()), "text": "",
                          "placement": placement.where(self._stack)}
        elif tag == "title":
            self._in_title = True
        if tag in VOID:
            return
        if tag in CLOSES_P and self._stack and self._stack[-1][0] == "p":
            self._stack.pop()
        self._stack.append((tag, f"{a.get('class') or ''} {a.get('id') or ''}".lower(), (a.get("role") or "").lower()))

    def handle_endtag(self, tag):
        open_tags = [t for t, _, _ in self._stack]
        if tag in open_tags:                 # close it and anything the page left open inside it
            del self._stack[len(open_tags) - 1 - open_tags[::-1].index(tag):]
        if tag in SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag == "a" and self._open:
            self._open["text"] = " ".join(self._open["text"].split())
            self.links.append(self._open)
            self._open = None
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
        if self._open is not None:
            self._open["text"] += data
        self.text.append(data)


def parse(html: str, base: str) -> dict:
    """{"title", "text", "links": [{"href" (absolute), "rel" (set), "text", "placement"}]}"""
    reader = _Reader()
    try:
        reader.feed(html)
    except Exception:  # noqa: BLE001 — a broken page still gives what was read before the break
        pass
    for link in reader.links:
        link["href"] = urllib.parse.urljoin(base, link["href"])
    links = [l for l in reader.links if l["href"].startswith(("http://", "https://"))]
    return {"title": " ".join(reader.title.split()), "text": " ".join(" ".join(reader.text).split()), "links": links}


def fetch(url: str) -> dict:
    """{"url", "final", "status", "html", "error", "blocked", "dead"}. Never raises.
    A site whose certificate fails is read over plain HTTP: parked domains often answer only there."""
    url = url if url.startswith(("http://", "https://")) else "https://" + url
    out = _get(url)
    if out["dead"] and "SSL" in out["error"] and url.startswith("https://"):
        plain = _get("http://" + url[len("https://"):])
        if not plain["dead"]:
            return {**plain, "error": out["error"]}
    return out


def _decode(raw: bytes, charset: str | None) -> str:
    """The page as text. A charset Python does not know reads as UTF-8: one site's header said
    "charset=utf-8, text/xml" (2026-10-15), and the LookupError stopped a whole vet run."""
    try:
        return raw.decode(charset or "utf-8", "replace")
    except LookupError:
        return raw.decode("utf-8", "replace")


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8", "Accept-Language": "en"})


def _reason(exc: BaseException) -> str:
    """Why no answer came, in one line: "TimeoutError: timed out"."""
    reason = getattr(exc, "reason", exc)
    return re.sub(r"\s+", " ", f"{type(reason).__name__}: {reason}")[:120]


def _get(url: str) -> dict:
    out = {"url": url, "final": url, "status": 0, "html": "", "error": "", "blocked": False, "dead": False}
    try:
        with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as res:
            out.update(status=res.status, final=res.geturl())
            try:
                raw = res.read(MAX_BYTES)
            except http.client.IncompleteRead as exc:       # the answer broke off: what came is still the page
                raw, out["error"] = exc.partial, "the answer broke off"
            out.update(html=_decode(raw, res.headers.get_content_charset()))
    except urllib.error.HTTPError as exc:
        out.update(status=exc.code, final=exc.geturl() or url, error=f"HTTP {exc.code}", blocked=exc.code not in GONE,
                   dead=exc.code in GONE)
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError, ValueError,
            http.client.HTTPException) as exc:
        out.update(error=_reason(exc), dead=True)
    return out


class _Hold(urllib.request.HTTPRedirectHandler):
    """Hands a redirect back, as the HTTP error urllib raises for it, instead of following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_Hold)


def _open(req: urllib.request.Request, timeout: float):
    """One request with no redirect followed (the seam the tests replace)."""
    return _OPENER.open(req, timeout=timeout)


def _step(url: str) -> dict:
    """{"status", "location", "error"} of one request. Never raises."""
    try:
        with _open(_request(url), TIMEOUT) as res:
            return {"status": res.status, "location": "", "error": ""}
    except urllib.error.HTTPError as exc:
        where = (exc.headers.get("Location") or "") if exc.headers else ""
        moved = exc.code in REDIRECTS and where.strip()
        return {"status": exc.code, "location": where.strip(), "error": "" if moved else f"HTTP {exc.code}"}
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError, ValueError) as exc:
        return {"status": 0, "location": "", "error": _reason(exc)}


def trace(url: str, hops: int = MAX_HOPS) -> dict:
    """{"url", "final", "status", "hops": [{"url", "status"}], "error", "loop"}: the redirects followed one at a time,
    so each one's status is known (urllib's own following hides them). "hops" are the redirects taken, each with the
    URL that answered it; "status" and "error" are those of the last answer. A redirect back to a URL already in the
    chain is a loop, and more than `hops` redirects are too many; both end the chain with an error. Never raises."""
    url = url if url.startswith(("http://", "https://")) else "https://" + url
    chain, current = [], url
    while True:
        got = _step(current)
        if got["status"] not in REDIRECTS or not got["location"]:
            return {"url": url, "final": current, "status": got["status"], "hops": chain, "error": got["error"], "loop": False}
        chain.append({"url": current, "status": got["status"]})
        current = urllib.parse.urljoin(current, got["location"])
        loop = any(h["url"] == current for h in chain)
        if loop or len(chain) > hops:
            return {"url": url, "final": current, "status": got["status"], "hops": chain, "loop": loop,
                    "error": "a redirect loop" if loop else f"more than {hops} redirects"}


def external(links: list[dict], home: str) -> list[dict]:
    """Links that leave the site."""
    own = site(home)
    return [l for l in links if site(l["href"]) != own]
