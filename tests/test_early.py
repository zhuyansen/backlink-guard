"""competitors --early: each competitor's first 90 days, the same-age table, the launch checklist. The backlink data
and the Wayback Machine are stubbed: no network."""
from datetime import date, timedelta

import pytest

from backlink_guard import competitors, early, report

TODAY = date(2026, 7, 1)
OWN, A, B = "mine.example", "rival-a.example", "rival-b.example"
LISTED = {"farm.example": {"category": "link-network", "family": "", "evidence": "x", "evidence_url": "https://farm.example/",
                           "last_checked": "2026-06-01"}}
ARCHIVED = {OWN: "2026-04-01", A: "2026-02-17", B: "2026-03-01"}


def rd(host, seen, lost=None, rank=40, pages=1, nofollow=0, spam=0, places=None):
    return {"domain": host, "first_seen": f"{seen} 10:00:00 +00:00", "lost_date": lost and f"{lost} 10:00:00 +00:00",
            "rank": rank, "referring_pages": pages, "referring_pages_nofollow": nofollow, "backlinks_spam_score": spam,
            "referring_links_semantic_locations": places or {"section": pages}}


EARLIEST = {
    A: [rd("launchdir.example", "2026-02-18"), rd("owner-site.example", "2026-02-18", pages=20, places={"footer": 17, "": 3}),
        rd("w1a.example", "2026-02-19"), rd("w1b.example", "2026-02-20"), rd("w1c.example", "2026-02-22"),
        rd("gone.example", "2026-02-23", lost="2026-05-15"), rd("nofollow.example", "2026-02-24", pages=2, nofollow=2),
        rd("spammy.example", "2026-03-01", spam=55), rd("farm.example", "2026-03-02"), rd("shared.example", "2026-03-05"),
        rd("yours-too.example", "2026-03-06"), rd("huge.example", "2026-03-15", pages=534, places={"": 534}),
        rd("late.example", "2026-06-01")],
    B: [rd("shared.example", "2026-03-10"), rd("yours-too.example", "2026-03-11"), rd("other-b.example", "2026-03-12")],
    OWN: [rd("yours-too.example", "2026-04-05"), rd("old.example", "2026-04-09", lost="2026-05-01")],
}
PAGES = {"shared.example": ("https://shared.example/new-tools", "New tools this week"),
         "launchdir.example": ("https://launchdir.example/launch/rival-a", "Rival A launches on LaunchDir")}


def world(monkeypatch):
    """The backlink data answering from the tables above; returns the calls made."""
    calls = []

    def answer(path, body):
        calls.append((path, body))
        if path == competitors.BACKLINKS:
            hosts = body["filters"][0][2]
            return {"items": [{"domain_from": h, "url_from": PAGES[h][0], "page_from_title": PAGES[h][1], "anchor": "x",
                               "dofollow": True} for h in hosts if h in PAGES]}, 25000
        items = EARLIEST.get(body["target"], [])
        return {"total_count": len(items), "items": items}, 25000
    monkeypatch.setattr(competitors.aisa, "rest", answer)
    monkeypatch.setattr(competitors.blocklist, "load", lambda fresh=False: LISTED)
    monkeypatch.setattr(early, "first_copy", lambda domain: ARCHIVED.get(domain, ""))
    return calls


def test_launch_is_the_first_copy_unless_the_domain_sat_unused_or_predates_the_index():
    one = [rd("x.example", "2026-02-10")]
    assert early.launch("a.example", one, date(2026, 2, 1))["from"] == "archive"
    assert early.launch("a.example", one, date(2026, 3, 1)) == {
        "day": "2026-02-10", "from": "first link", "archived": "2026-03-01", "first_link": "2026-02-10",
        "dormant": False, "before_index": False}                       # a link before the first copy: launched by then
    parked = early.launch("a.example", one, date(2020, 1, 1))
    assert (parked["day"], parked["dormant"]) == ("2026-02-10", True)
    assert early.launch("a.example", [rd("x.example", "2019-01-15")], date(2010, 5, 1))["before_index"]
    assert early.launch("a.example", one, None)["from"] == "first link"


def test_a_count_past_the_end_of_the_list_read_is_a_floor():
    items = [rd(f"s{i}.example", d) for i, d in enumerate(("2026-01-02", "2026-01-20", "2026-02-10"))]
    got = early.counts(items, date(2026, 1, 1), total=10)
    assert got[30] == {"n": 2, "exact": True} and got[60] == {"n": 3, "exact": False} and not got[90]["exact"]
    assert early.counts(items, date(2026, 1, 1), total=3)[90] == {"n": 3, "exact": True}


def test_a_launch_week_burst_and_no_burst_in_an_even_spread():
    start = date(2026, 2, 17)
    launch_week = [rd(f"w{i}.example", (start + timedelta(days=i)).isoformat()) for i in range(6)] + [rd("x.example", "2026-03-20")]
    got = early.bursts(launch_week, start)
    assert [(b["week"], b["n"]) for b in got] == [(1, 6)] and "w0.example" in got[0]["sites"]
    even = [rd(f"e{i}.example", (start + timedelta(days=7 * i)).isoformat()) for i in range(12)]
    assert early.bursts(even, start) == []


def test_lost_nofollow_and_site_wide_links_count_apart_from_the_channels():
    rows, others = early.early_rows(A, EARLIEST[A], date(2026, 2, 17))
    sites = [r["site"] for r in rows]
    assert "launchdir.example" in sites and "late.example" not in sites            # after the first 90 days
    assert others == {"lost": 1, "nofollow": 1, "sitewide": ["huge.example", "owner-site.example"]}


def test_the_checklist_is_what_two_competitors_got_early_and_you_lack(monkeypatch):
    calls = world(monkeypatch)
    r = early.early(OWN, [A, B], vetted=0, today=TODAY)
    assert list(r["sites"]) == [OWN, A, B]
    a = r["sites"][A]
    assert a["launch"]["day"] == "2026-02-17" and a["counts"][30] == {"n": 12, "exact": True}
    assert [x["site"] for x in a["rows"]] == ["launchdir.example", "w1a.example", "w1b.example", "w1c.example", "shared.example"]
    assert a["yours"] == ["yours-too.example"]
    assert {d["site"] for d in r["dropped"]} == {"farm.example", "spammy.example"}
    assert [(x["site"], x["rivals"]) for x in r["checklist"]] == [("shared.example", [A, B])]
    assert r["checklist"][0]["young"] == {"rival": B, "age_days": 9, "on": "2026-03-10", "recent": True}
    assert r["checklist"][0]["example"]["url"] == "https://shared.example/new-tools"
    assert [b["week"] for b in a["bursts"]] == [1]
    assert [body["target"] for path, body in calls if path == competitors.REFERRING] == [OWN, A, B]   # yours read in full:
    assert r["cost"] == 25000 * len(calls) and not r["errors"]                                        # no "links to you?" call


def test_the_cap_leaves_competitors_out_and_says_so(monkeypatch):
    world(monkeypatch)
    r = early.early(OWN, [A, B], max_usd=0.10, vetted=0, today=TODAY)   # $0.025 spent a call, $0.06 held for the next
    assert list(r["sites"]) == [OWN, A] and r["left_out"] == [f"the earliest referring domains of {B}"]


def test_the_report_reads_the_same_age_table_and_the_checklist(monkeypatch):
    world(monkeypatch)
    text = report.early(early.early(OWN, [A, B], vetted=0, today=TODAY))
    assert "| **mine.example** (you) | 2026-04-01 (first archived copy) |" in text
    assert "| shared.example | rival-a.example, rival-b.example | 2026-03-05 |" in text
    assert "✅ rival-b.example at 9 days (2026-03-10)" in text
    assert "site-wide, mostly its owner's other sites or partners and not channels: huge.example, owner-site.example" in text
    assert "rival-a.example, week 1 (from 2026-02-17)" in text
    assert "On the shared spam-link list: 1: farm.example." in text


def test_the_checklist_gets_a_free_vet_with_whether_it_takes_new_sites(monkeypatch):
    world(monkeypatch)
    seen = {}

    def vet(sites, **kwargs):
        seen.update(sites=sites, **kwargs)
        return {"rows": [{"domain": s, "grade": "ok", "action": "submit", "newcomers": {"young": 2, "dated": 5, "unknown": ""}}
                         for s in sites]}
    monkeypatch.setattr("backlink_guard.vet.vet", vet)
    r = early.early(OWN, [A, B], vetted=10, today=TODAY)
    assert seen["sites"] == ["shared.example"] and seen["paid_sources"] is False and seen["newcomers"] is True
    assert r["checklist"][0]["vet"] == {"grade": "ok", "action": "submit", "takes_new": {"young": 2, "dated": 5, "unknown": ""}}
    assert r["vetted"] == 1 and "✅ submit; 2/5 new" in report.early(r)


def test_the_mcp_tool_reads_the_earliest_links_with_early(monkeypatch):
    pytest.importorskip("mcp")
    from backlink_guard import mcp_server
    world(monkeypatch)
    monkeypatch.setattr(early, "date", type("Today", (date,), {"today": staticmethod(lambda: TODAY)}))
    got = mcp_server._competitors(OWN, [A, B], 7, 100, None, early=True, vetted=0)
    assert got["checklist"] == 1 and "## Launch checklist" in got["report_markdown"] and got["cost_usd"] == 0.125
