"""audit, 0.8: the referring domains one owner runs, by the accounts their home pages report to. No network."""
import urllib.parse
from datetime import date

from backlink_guard import links, owners, page, policy, profile, report, seen, vet

TODAY = date(2026, 10, 20)
PUB = "ca-pub-5550001112223334"
HOMES = {"a.example": f'<ins data-ad-client="{PUB}"></ins>',
         "b.example": f'<script>(adsbygoogle=window.adsbygoogle||[]).push({{}})</script><ins data-ad-client="{PUB}"></ins>',
         "c.example": f'<ins data-ad-client="{PUB}"></ins><script>gtag("config", "G-XXXXXXXXXX")</script>',
         "d.example": '<script>gtm("GTM-AB12CD")</script>',
         "e.example": '<script async src="https://www.googletagmanager.com/gtag/js?id=G-ABC123DEF4"></script>',
         "f.example": '<script async src="https://www.googletagmanager.com/gtag/js?id=G-ABC123DEF4"></script>',
         "g.example": "<p>No accounts here.</p>"}


def rows_from(counts):
    """{site: links to you}, as the audit counts them from its backlink rows."""
    return owners.by_links([links.row(f"https://{s}/p{i}", "https://mine.example/", "Mine", 10)
                            for s, n in counts.items() for i in range(n)])


def homes(asked=None):
    def fetch(url):
        site = page.host(url)
        (asked if asked is not None else []).append(site)
        return {"url": url, "final": url, "status": 200, "html": HOMES.get(site, ""), "error": "", "blocked": False, "dead": False}
    return fetch


def test_three_referring_domains_on_one_account_are_one_owners_network():
    asked = []
    got = owners.networks(rows_from({"a.example": 5, "b.example": 2, "c.example": 1, "d.example": 9, "e.example": 1,
                                     "f.example": 1, "g.example": 3}), today=TODAY, fetch=homes(asked))
    assert asked[0] == "d.example" and got["read"] == 7 and got["with_accounts"] == 6       # the most links first
    [group] = got["groups"]                                                                  # e and f: two are not three
    assert group == {"key": f"adsense:{PUB}", "sites": ["a.example", "b.example", "c.example"], "earlier": [], "links": 8,
                     "listed": []}
    assert got["flag"]["flag"] == "owner_network" and got["flag"]["level"] == "caution"
    assert got["flag"]["evidence"] == (f"3 referring domains in 1 network: adsense:{PUB} on a.example, b.example, c.example, "
                                       "8 links. Count each network as one source")
    assert got["flag"]["policy"] == policy.AUTOMATED and got["networks"] == [] and got["errors"] == []
    kept = seen.load()["ids"]
    assert set(kept[f"adsense:{PUB}"]) == {"a.example", "b.example", "c.example"} and "ga4:G-ABC123DEF4" in kept   # for vet


def test_sites_from_earlier_checks_count_and_two_must_link_to_you():
    store = seen.load()
    seen.record(store, "ids", {"ga4:G-ABC123DEF4": ["x.example"], f"adsense:{PUB}": ["y.example", "z.example"]}, TODAY)
    seen.save(store)
    got = owners.networks(rows_from({"e.example": 1, "f.example": 2, "a.example": 1}), today=TODAY, fetch=homes())
    assert [(g["key"], g["sites"], g["earlier"]) for g in got["groups"]] == [("ga4:G-ABC123DEF4", ["e.example", "f.example"], ["x.example"])]
    assert "(and 1 from earlier checks)" in got["flag"]["evidence"]                      # a alone links to you: not counted


def test_a_network_mostly_on_the_shared_list_comes_with_a_report_for_the_rest(monkeypatch):
    entry = {"category": "link-network", "family": "", "evidence": "x", "evidence_url": "https://a.example/", "last_checked": "2026-10-16"}
    monkeypatch.setattr(owners.blocklist, "load", lambda fresh=False: {"a.example": entry, "b.example": entry})
    got = owners.networks(rows_from({"a.example": 1, "b.example": 1, "c.example": 1}), today=TODAY, fetch=homes())
    assert got["groups"][0]["listed"] == ["a.example", "b.example"]
    [network] = got["networks"]
    assert network["unlisted"] == ["c.example"] and "domain=c.example" in urllib.parse.unquote(network["report"])
    monkeypatch.setattr(owners.blocklist, "load", lambda fresh=False: (_ for _ in ()).throw(OSError("HTTP Error 404")))
    unread = owners.networks(rows_from({"a.example": 1, "b.example": 1, "c.example": 1}), today=TODAY, fetch=homes())
    assert unread["networks"] == [] and unread["errors"] == ["spam list: HTTP Error 404"] and unread["groups"]


def test_audit_reads_the_home_pages_and_shows_the_networks(monkeypatch):
    items = [{"url_from": f"https://{s}/p{i}", "url_to": "https://mine.example/", "anchor": "Mine", "domain_from_rank": 50}
             for s in ("a.example", "b.example", "c.example", "g.example") for i in range(2)]

    def call(tool, args):
        if tool == links.TOOL:
            return {"total_count": 8, "items": items}, 60000
        return {"items": []}, 25000
    monkeypatch.setattr(vet.aisa, "key", lambda: "k")
    monkeypatch.setattr(vet.aisa, "call", call)
    monkeypatch.setattr(vet.goanyapi, "key", lambda: "")
    monkeypatch.setattr(page, "fetch", homes())
    a = profile.audit("mine.example", today=TODAY)
    assert a["owners"]["read"] == 4 and a["owners"]["groups"][0]["links"] == 6
    assert [f["flag"] for f in a["flags"]] == ["owner_network"]
    text = report.audit(a)
    assert "## One owner's sites among your referring domains" in text
    assert "Home pages of 4 referring domains read; 3 report to an analytics or ads account." in text
    assert f"| adsense:{PUB} | a.example, b.example, c.example | 6 | – | – |" in text and "one owner's votes" in text
    assert profile.audit("mine.example", today=TODAY, homes=0)["owners"] == {}             # --homes 0 reads none


def test_audit_fills_up_from_the_referring_domains_list_when_its_backlinks_name_few_sites(monkeypatch):
    items = [{"url_from": f"https://a.example/p{i}", "url_to": "https://mine.example/", "anchor": "Mine", "domain_from_rank": 50,
              "semantic_location": "footer"} for i in range(30)]                        # one site-wide source
    asked = []

    def call(tool, args):
        asked.append(tool)
        if tool == links.TOOL:
            return {"total_count": 30, "items": items}, 60000
        if tool == owners.REFERRING_TOOL:
            assert args["limit"] == owners.HOMES and args["order_by"] == ["rank,desc"]
            return {"items": [{"domain": "a.example", "backlinks": 30}, {"domain": "b.example", "backlinks": 2},
                              {"domain": "www.c.example", "backlinks": 1}]}, 34800
        return {"items": []}, 25000
    monkeypatch.setattr(vet.aisa, "key", lambda: "k")
    monkeypatch.setattr(vet.aisa, "call", call)
    monkeypatch.setattr(vet.goanyapi, "key", lambda: "")
    monkeypatch.setattr(page, "fetch", homes())
    a = profile.audit("mine.example", today=TODAY)
    assert a["owners"]["read"] == 3 and a["owners"]["groups"][0]["sites"] == ["a.example", "b.example", "c.example"]
    assert a["owners"]["groups"][0]["links"] == 33 and a["cost"] == 60000 + 25000 + 34800
    again = profile.audit("mine.example", today=TODAY)
    assert again["cost"] == 0 and asked.count(owners.REFERRING_TOOL) == 1                   # kept 7 days


def test_a_cloudflare_web_analytics_token_is_an_account_too():
    single = ("<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js/v1\" "
              "data-cf-beacon='{\"version\":\"2024.11.0\",\"token\":\"1927ffdf93a646bd82ea6623b4b0e0f8\",\"r\":1}'></script>")
    escaped = '<script data-cf-beacon="{&quot;token&quot;: &quot;0a1b2c3d4e5f60718293a4b5c6d7e8f9&quot;}" src="x"></script>'
    assert vet.ids_of(single) == ["cloudflare:1927ffdf93a646bd82ea6623b4b0e0f8"]
    assert vet.ids_of(escaped) == ["cloudflare:0a1b2c3d4e5f60718293a4b5c6d7e8f9"]
    assert vet.ids_of('<script data-cf-beacon=\'{"token": "not-a-token"}\'></script>') == []
