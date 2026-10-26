"""lost, 0.8: pages of yours that redirect, followed one hop at a time. Pages answer from tables: no network."""
import io
import urllib.error

from backlink_guard import links, lost, page, policy, report

SITE = "https://mine.example"


def hopping(monkeypatch, table):
    """page._open answering from {path: status or (status, Location)}; returns the URLs asked."""
    asked = []

    class Response(io.BytesIO):
        def __init__(self, status):
            super().__init__(b"")
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def open_(req, timeout):
        asked.append(req.full_url)
        got = table.get(req.full_url.removeprefix(SITE), 404)
        status, location = got if isinstance(got, tuple) else (got, "")
        if status == "down":
            raise urllib.error.URLError(TimeoutError("timed out"))
        if status >= 300:
            raise urllib.error.HTTPError(req.full_url, status, "x", {"Location": location} if location else {}, io.BytesIO(b""))
        return Response(status)
    monkeypatch.setattr(page, "_open", open_)
    return asked


def test_trace_reads_each_hop_and_where_it_ends(monkeypatch):
    hopping(monkeypatch, {"/zh/weekly": (308, "/zh/go-global/weekly"), "/zh/go-global/weekly": 200,
                          "/old": (302, "https://mine.example/older"), "/older": (301, "/zh/weekly")})
    got = page.trace(SITE + "/zh/weekly")                                  # a relative Location, as the site sends it
    assert got["hops"] == [{"url": SITE + "/zh/weekly", "status": 308}] and got["final"] == SITE + "/zh/go-global/weekly"
    assert (got["status"], got["error"], got["loop"]) == (200, "", False)
    chain = page.trace(SITE + "/old")
    assert [h["status"] for h in chain["hops"]] == [302, 301, 308] and chain["final"] == SITE + "/zh/go-global/weekly"


def test_a_loop_too_many_hops_and_a_redirect_with_no_location_end_the_chain(monkeypatch):
    table = {"/a": (301, "/b"), "/b": (302, "/a"), "/bare": (301, "")}
    table.update({f"/h{i}": (301, f"/h{i + 1}") for i in range(12)})
    hopping(monkeypatch, table)
    loop = page.trace(SITE + "/a")
    assert loop["loop"] and loop["error"] == "a redirect loop" and len(loop["hops"]) == 2
    long = page.trace(SITE + "/h0")
    assert long["error"] == f"more than {page.MAX_HOPS} redirects" and len(long["hops"]) == page.MAX_HOPS + 1
    bare = page.trace(SITE + "/bare")
    assert bare["hops"] == [] and (bare["status"], bare["error"]) == (301, "HTTP 301")


def test_states_of_pages_that_redirect(monkeypatch):
    hopping(monkeypatch, {"/live": 200, "/moved": (301, "/new"), "/new": 200, "/moved-gone": (301, "/gone"),
                          "/loop": (301, "/loop"), "/to-error": (302, "/busy"), "/busy": 503, "/refused": 403,
                          "/to-nothing": (301, "/down"), "/down": "down"})
    states = {u: lost.status(SITE + u) for u in ("/live", "/moved", "/moved-gone", "/loop", "/to-error", "/refused", "/to-nothing")}
    assert {u: s["state"] for u, s in states.items()} == {
        "/live": "live", "/moved": "redirected", "/moved-gone": "dead", "/loop": "broken", "/to-error": "broken",
        "/refused": "blocked", "/to-nothing": "broken"}
    assert states["/to-error"]["error"] == "HTTP 503" and states["/to-nothing"]["error"].startswith("TimeoutError")


def moved(path, final, *codes, state="redirected", error=""):
    return {"url": SITE + path, "final": final if "://" in final else SITE + final, "state": state, "error": error,
            "hops": [{"url": "", "status": c} for c in codes]}


def test_verdicts_worst_first():
    verdict = lambda d: (lambda j: (j["verdict"], j["why"]))(lost.judge(d, "mine.example"))  # noqa: E731
    assert verdict(moved("/zh/weekly", "/zh/go-global/weekly", 308)) == ("fine", [])    # the move this tool's maker made
    assert verdict(moved("/blog/post", "/blog/post/", 301)) == ("fine", [])
    assert verdict(moved("/guide", "/guides/guide", 302)) == ("temporary", ["302, a temporary redirect"])
    assert verdict(moved("/guide", "/guides/guide", 301, 301)) == ("chain", ["2 redirects in a row"])
    assert verdict(moved("/blog/old-post", "/", 301)) == ("soft_lost", ["ends on your home page"])
    assert verdict(moved("/pricing", "/zh/", 301)) == ("soft_lost", ["ends on your home page"])      # a language root
    assert verdict(moved("/", "/en/", 302)) == ("temporary", ["302, a temporary redirect"])            # home to home
    assert verdict(moved("/tools/csv", "https://other.example/csv", 301)) == ("soft_lost", ["ends on another site, other.example"])
    unrelated = verdict(moved("/tools/csv-cleaner", "/about-us", 301))
    assert unrelated[0] == "soft_lost" and unrelated[1][0].startswith("ends on /about-us, a path that matches it 0.")
    assert verdict(moved("/old", "/", 302, 301)) == ("soft_lost", ["ends on your home page", "302, a temporary redirect",
                                                                   "2 redirects in a row"])
    assert verdict(moved("/a", "/a", 301, 301, state="broken", error="a redirect loop")) == ("broken", ["a redirect loop"])


def test_lost_lists_redirects_next_to_dead_links_with_a_page_for_the_soft_lost(monkeypatch):
    targets = ["/zh/weekly", "/old-post", "/tmp", "/gone", "/loop"]
    rows = [links.row(f"https://r{i}.example/x", SITE + t, "Mine", 100) for i, t in enumerate(targets)]
    rows.append(links.row("https://q.example/y", SITE + "/old-post", "Mine", 50))
    monkeypatch.setattr(lost.links, "fetch", lambda domain, fresh, limit=1000, top=None: {
        "rows": rows, "total": 6, "source": "AIsa", "strength": "AIsa rank", "cost": 30000, "errors": []})
    answers = {SITE + "/zh/weekly": moved("/zh/weekly", "/zh/go-global/weekly", 308),
               SITE + "/old-post": moved("/old-post", "/", 301), SITE + "/tmp": moved("/tmp", "/tmp-new", 302),
               SITE + "/gone": {"state": "dead", "status": 404, "final": SITE + "/gone", "error": "HTTP 404", "hops": []},
               SITE + "/loop": moved("/loop", "/loop", 301, 301, state="broken", error="a redirect loop")}
    check = lambda url: {"url": url, "status": 301, **answers.get(url, {"state": "live", "status": 200, "final": url,  # noqa: E731
                                                                      "error": "", "hops": []})}
    sitemap = lambda domain: [SITE + "/blog/old-post-renamed", SITE + "/zh/go-global/weekly"]       # noqa: E731
    r = lost.lost("mine.example", check=check, sitemap=sitemap)
    assert [(d["url"].removeprefix(SITE), d["verdict"]) for d in r["redirected"]] == [
        ("/loop", "broken"), ("/old-post", "soft_lost"), ("/tmp", "temporary"), ("/zh/weekly", "fine")]
    soft = r["redirected"][1]
    assert soft["suggest"]["url"] == SITE + "/blog/old-post-renamed" and soft["domains"] == 2
    assert [d["url"] for d in r["dead"]] == [SITE + "/gone"] and r["sitemap"] == 2
    assert {f["flag"] for f in r["flags"]} == {"dead_target", "soft_lost", "weak_redirect", "broken_redirect"}
    assert "2 referring domains: /old-post: ends on your home page" in next(f for f in r["flags"] if f["flag"] == "soft_lost")["evidence"]
    text = report.lost(r)
    assert "## Pages of yours that redirect" in text
    assert "| /old-post | 301 → / | 2 | 2 | 🔻 soft-lost: ends on your home page | 301 to /blog/old-post-renamed | 0.62 |" in text
    assert "| /loop | 301 → 301 → /loop | 1 | 1 | ⛔ broken: a redirect loop | – | – |" in text
    assert "| /tmp | 302 → /tmp-new | 1 | 1 | ⚠️ temporary: 302, a temporary redirect | – | – |" in text
    assert "Redirected well (one permanent hop to a page like it): 1 page(s), e.g. /zh/weekly → /zh/go-global/weekly." in text
    assert "might be treated as a soft 404 error" in text and policy.SITE_MOVE_URL in text
