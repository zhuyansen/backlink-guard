"""vet --newcomers: whether a source's newest pages link to new sites. Its pages, RDAP and the Wayback Machine are
stubbed: no network."""
import io
import json
from datetime import date

from backlink_guard import newcomers, report

SITEMAP = """<?xml version="1.0"?><urlset>
<url><loc>https://dir.example/</loc><lastmod>2026-10-21</lastmod></url>
<url><loc>https://dir.example/tools/alpha</loc><lastmod>2026-10-20</lastmod></url>
<url><loc>https://dir.example/tools/beta</loc><lastmod>2026-10-18T09:00:00+00:00</lastmod></url>
<url><loc>https://dir.example/about</loc><lastmod>2026-01-05</lastmod></url>
<url><loc>https://dir.example/undated</loc></url>
</urlset>"""
NAV = '<nav><a href="https://social.example/dir">Follow us</a></nav>'
FOOT = '<footer><a href="https://sponsor.example">Our sponsor</a></footer>'
PAGES = {
    "https://dir.example/tools/alpha": f'<html><body>{NAV}<main><p>Try <a href="https://new-one.example/">New One</a> or '
                                       f'<a href="https://old-one.example">Old One</a>, built on <a href="https://host.example">Host</a>.</p>'
                                       f'<a href="https://dir.example/go/12">Visit</a></main>{FOOT}</body></html>',
    "https://dir.example/tools/beta": f'<html><body>{NAV}<main><p><a href="https://new-two.example">New Two</a> on '
                                      f'<a href="https://host.example">Host</a></p></main>{FOOT}</body></html>',
    "https://dir.example/about": '<html><body><main><p>Since 2019. <a href="https://old-one.example">Old One</a> and '
                                 '<a href="https://host.example">Host</a></p></main></body></html>',
}
BORN = {"new-one.example": ("2026-09-01", "registered"), "new-two.example": ("2026-08-15", "registered"),
        "old-one.example": ("2019-05-05", "registered")}


def answer(url, html="", dead=False):
    return {"url": url, "final": url, "status": 0 if dead else 200, "html": html, "error": "", "blocked": False, "dead": dead}


def world(monkeypatch, robots="Sitemap: https://dir.example/sitemap.xml", sitemap=SITEMAP, pages=PAGES):
    asked = []

    def fetch(url):
        asked.append(url)
        if url.endswith("/robots.txt"):
            return answer(url, robots)
        if url.endswith("sitemap.xml"):
            return answer(url, sitemap) if sitemap else answer(url, dead=True)
        return answer(url, pages[url]) if url in pages else answer(url, dead=True)
    monkeypatch.setattr(newcomers.page, "fetch", fetch)
    monkeypatch.setattr(newcomers, "born", lambda domain: BORN.get(domain, ("", "")))
    return asked


def test_the_newest_dated_pages_come_first_and_the_home_page_is_left_out():
    pages = newcomers.dated(SITEMAP)
    assert ("https://dir.example/undated", "") not in pages and len(pages) == 4
    assert newcomers.newest(pages, "dir.example", 2) == [("https://dir.example/tools/alpha", "2026-10-20"),
                                                          ("https://dir.example/tools/beta", "2026-10-18")]


def test_listed_sites_come_from_body_links_to_other_sites():
    sites = newcomers.listed_sites(PAGES["https://dir.example/tools/alpha"], "https://dir.example/tools/alpha")
    assert sites == {"new-one.example", "old-one.example", "host.example"}        # not the nav, the footer, its own /go/


def test_a_source_whose_new_pages_link_to_new_sites_takes_new_sites(monkeypatch):
    world(monkeypatch)
    got = newcomers.takes_new("dir.example", date(2026, 10, 27))
    assert (got["pages"], got["sites"], got["dated"], got["young"], got["share"]) == (3, 3, 3, 2, 0.67)
    assert got["unknown"] == "" and got["newest"] == "2026-10-20"
    assert [(e["site"], e["age_days"]) for e in got["examples"]] == [("new-one.example", 49), ("new-two.example", 64)]
    assert "2 of 3 sites its newest pages link to were registered under 6 months before: new-one.example (49 days)" \
        in report.takes_new_text(got)                                     # host.example is on every page: furniture


def test_what_it_cannot_tell_it_says(monkeypatch):
    world(monkeypatch, sitemap=SITEMAP.replace("<lastmod>", "<changed>").replace("</lastmod>", "</changed>"))
    assert newcomers.takes_new("dir.example")["unknown"] == "its sitemaps carry no dates"
    world(monkeypatch, sitemap="")
    assert newcomers.takes_new("dir.example")["unknown"] == "no readable sitemap"
    wrapped = {u: '<html><body><main><p><a href="https://dir.example/go/1">Visit</a></p></main></body></html>' for u in PAGES}
    world(monkeypatch, pages=wrapped)
    assert newcomers.takes_new("dir.example")["unknown"].startswith("its newest pages link to no other site")


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def rdap(monkeypatch, *answers):
    """urlopen answering RDAP requests in turn: a dict is the reply, an int an HTTP error; returns the URLs asked."""
    calls, left = [], list(answers)

    def urlopen(req, timeout):
        calls.append(req.full_url)
        got = left.pop(0)
        if isinstance(got, int):
            raise newcomers.urllib.error.HTTPError(req.full_url, got, "no", {}, None)
        return Reply(json.dumps(got).encode())
    monkeypatch.setattr(newcomers.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(newcomers, "RDAP_GAP", 0)
    monkeypatch.setattr(newcomers, "RETRY_PAUSE", 0)
    return calls


def test_rdap_gives_the_registration_day_once_a_month(monkeypatch):
    calls = rdap(monkeypatch, {"events": [{"eventAction": "last changed", "eventDate": "2026-09-01T00:00:00Z"},
                                          {"eventAction": "registration", "eventDate": "2026-08-09T03:00:00Z"}]})
    assert newcomers.registered("new.example") == ("2026-08-09", "ok") == newcomers.registered("new.example")
    assert calls == ["https://rdap.org/domain/new.example"]


def test_the_first_archived_copy_dates_a_site_only_for_registries_without_rdap(monkeypatch):
    monkeypatch.setattr(newcomers, "first_copy", lambda domain: "2026-07-01")
    rdap(monkeypatch, 404)
    assert newcomers.born("tool.example") == ("2026-07-01", "first archived")
    calls = rdap(monkeypatch, 429, 503)                     # asked twice, then left undated: a first copy can come
    assert newcomers.born("busy.example") == ("", "")       # years after the registration
    assert len(calls) == 2 and newcomers.cache.get("rdap:busy.example") is None
