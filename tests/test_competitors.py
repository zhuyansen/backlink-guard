"""competitors: each competitor's new referring domains and the link intersect. AIsa is stubbed: no network."""
import urllib.parse
from datetime import date

from backlink_guard import competitors, report

TODAY = date(2026, 10, 20)
OWN, A, B, C = "mine.example", "competitor-a.example", "competitor-b.example", "competitor-c.example"
LISTED = {"farm.example": {"category": "link-network", "family": "", "evidence": "x", "evidence_url": "https://farm.example/",
                           "last_checked": "2026-10-16"}}
TEMPLATE = "Premium Link Experts Providing Strategic Growth"


def refdomain(host, rank, spam=5, first_seen="2026-10-15 08:00:00 +00:00"):
    return {"domain": host, "rank": rank, "first_seen": first_seen, "backlinks": 3, "backlinks_spam_score": spam}


def both(host, ranks, spam=5, seen=("2026-09-01 10:00:00 +00:00", "2026-09-05 10:00:00 +00:00", "2026-09-09 10:00:00 +00:00")):
    """An intersection row: the host linking to the rivals numbered in `ranks` ({"1": rank, ...})."""
    return {"domain_intersection": {k: {"target": host, "rank": r, "first_seen": seen[(int(k) - 1) % len(seen)],
                                        "backlinks_spam_score": spam} for k, r in ranks.items()},
            "summary": {"intersections_count": len(ranks)}}


NEW = {A: [refdomain("dir-one.example", 310), refdomain("farm.example", 500), refdomain(OWN, 50), refdomain(B, 400),
           refdomain("already.example", 90), refdomain("quiet.example", 0), refdomain("spammy.example", 0, spam=55),
           refdomain("net-one.example", 0, spam=45), refdomain("net-two.example", 0, spam=45),
           refdomain("net-three.example", 0, spam=45), refdomain("blog.example", 0, spam=20)],
       B: [refdomain("github.com", 900)]}
SHARED = [both("lists.example", {"1": 40, "2": 200}), both("everyone.example", {"1": 10, "2": 0, "3": 5}),
          both("farm.example", {"1": 70, "3": 70}), both("single.example", {"2": 99})]
PAGES = {"www.dir-one.example": ("https://www.dir-one.example/tools/competitor-a", "Competitor A – Dir One | AI tools directory"),
         "github.com": ("https://github.com/someone/awesome-agent-tools", "awesome-agent-tools: a curated list"),
         "lists.example": ("https://lists.example/best-agent-tools", "The 12 best agent tools in 2026"),
         "everyone.example": ("https://everyone.example/blog/what-we-use", "What we use"),
         "blog.example": ("https://blog.example/posts/agents", "Agents I use"),
         **{f"net-{n}.example": (f"https://net-{n}.example/dir/growth-191458", TEMPLATE) for n in ("one", "two", "three")}}


def world(monkeypatch, cost=25000, fail=()):
    """aisa.rest answering from the tables above; returns the list of calls made."""
    calls = []

    def rest(path, body):
        calls.append((path, body))
        if path in fail:
            raise competitors.aisa.AisaError("Internal Server Error.")
        if path == competitors.INTERSECTION:
            return {"total_count": 86, "items": SHARED}, cost
        if path == competitors.BACKLINKS:
            hosts = body["filters"][0][2]
            return {"items": [{"domain_from": h, "url_from": PAGES[h][0], "page_from_title": PAGES[h][1], "anchor": "x",
                               "dofollow": True} for h in hosts if h in PAGES]}, cost
        if body["target"] == OWN:                                   # which of them already link to you
            return {"items": [{"domain": "already.example"}]}, cost
        return {"total_count": 40, "items": NEW.get(body["target"], [])}, cost
    monkeypatch.setattr(competitors.aisa, "rest", rest)
    monkeypatch.setattr(competitors.blocklist, "load", lambda fresh=False: LISTED)
    return calls


def test_new_sites_and_the_intersect_each_with_a_linking_page(monkeypatch):
    calls = world(monkeypatch)
    r = competitors.competitors(OWN, [A, B, C], today=TODAY)
    new_a = r["new"][A]
    assert [x["site"] for x in new_a["rows"]] == ["dir-one.example", "quiet.example", "blog.example"]   # rank, then low spam
    assert new_a["linking_you"] == ["already.example"] and new_a["total"] == 40
    assert new_a["rows"][0]["example"]["url"] == "https://www.dir-one.example/tools/competitor-a"   # found under www.
    assert new_a["rows"][0]["kind"] == "directory" and new_a["rows"][1]["example"] is None
    assert r["new"][B]["rows"][0]["kind"] == "list"                                          # an awesome list on GitHub
    shared = r["shared"]["rows"]
    assert [(x["site"], x["rivals"]) for x in shared] == [("everyone.example", [A, B, C]), ("lists.example", [A, B])]
    assert shared[1]["rank"] == 200 and shared[1]["first_seen"] == "2026-09-01" and shared[1]["kind"] == "list"
    assert r["dropped"] == [{"site": "farm.example", "why": "listed"}, {"site": "spammy.example", "why": "spam score 55"}]
    [network] = r["networks"]
    assert network["sites"] == ["net-one.example", "net-three.example", "net-two.example"] and network["kind"] == "template"
    assert "title=Report: net-one.example and 2 more" in urllib.parse.unquote(network["report"])
    first = calls[0][1]
    assert first["filters"] == [["first_seen", ">=", "2026-10-13 00:00:00 +00:00"]] and first["order_by"] == ["rank,desc"]
    intersect = next(body for path, body in calls if path == competitors.INTERSECTION)
    assert intersect["targets"] == {"1": A, "2": B, "3": C} and intersect["exclude_targets"] == [OWN]
    assert intersect["intersection_mode"] == "partial"
    lookup = next(body for path, body in calls if path == competitors.BACKLINKS and body["target"] == A)
    assert {"dir-one.example", "www.dir-one.example"} <= set(lookup["filters"][0][2])
    assert len(calls) == 3 + 1 + 1 + 2 and r["cost"] == 7 * 25000 and r["left_out"] == [] and r["errors"] == []


def test_the_report_names_the_sites_their_pages_and_what_was_left_out(monkeypatch):
    world(monkeypatch)
    text = report.competitors(competitors.competitors(OWN, [A, B], today=TODAY))
    assert f"### {A}: 40 new referring domains; 1 already link to you, left out" in text
    assert ("| dir-one.example | 310 | 2026-10-15 | [Competitor A – Dir One \\| AI tools directory]"
            "(https://www.dir-one.example/tools/competitor-a) | directory |") in text
    assert f"| lists.example | {A}, {B} | 200 | 2026-09-01 |" in text
    assert "- directory: Submit, after `vet` says it is worth it" in text and "Never pay for a followed link" in text
    assert "- On the shared spam-link list: 1: farm.example." in text
    assert "- Links to the competitor scoring 50 or more for spam: 1: spammy.example (55)." in text
    assert "- 3 sites whose linking pages share one title, \"{site} premium link experts" not in text     # own name kept out
    assert "3 sites whose linking pages share one title, \"premium link experts providing strategic growth\"" in text
    assert "[Report them](https://github.com/zhuyansen/backlink-spam-list/issues/new?" in text and "(cap $0.30)" in text


def test_the_cap_leaves_out_what_does_not_fit_and_says_so(monkeypatch):
    calls = world(monkeypatch)
    r = competitors.competitors(OWN, [A, B], today=TODAY, max_usd=0.06)       # two calls at about $0.028 each
    assert len(calls) == 2 and r["cost"] == 50000 and set(r["new"]) == {A, B}
    assert r["left_out"] == [f"which of them already link to {OWN}", "the link intersect", f"the linking pages of {A}",
                             f"the linking pages of {B}"]
    assert r["shared"] is None and r["networks"] == []
    text = report.competitors(r)
    assert "**Not asked, over the cap of $0.06:** which of them" in text and "Raise --max-usd" in text
    assert "Not read: see below." in text


def test_answers_cached_this_week_are_free_under_any_cap(monkeypatch):
    world(monkeypatch)
    first = competitors.competitors(OWN, [A, B], today=TODAY)
    calls = world(monkeypatch)
    again = competitors.competitors(OWN, [A, B], today=TODAY, max_usd=0)
    assert calls == [] and again["cost"] == 0 and again["left_out"] == []
    assert again["shared"]["rows"] == first["shared"]["rows"] and again["new"][A]["rows"] == first["new"][A]["rows"]


def test_one_competitor_has_no_intersect_and_a_failure_is_said(monkeypatch):
    calls = world(monkeypatch, fail=(competitors.BACKLINKS,))
    r = competitors.competitors(OWN, [A, OWN, "www." + A], today=TODAY)                  # yours and a repeat dropped
    assert r["rivals"] == [A] and r["shared"] is None
    assert not any(path == competitors.INTERSECTION for path, _ in calls)
    assert r["errors"] == [f"linking pages of {A}: Internal Server Error."] and r["new"][A]["rows"][0]["example"] is None
    text = report.competitors(r)
    assert "The link intersect needs two competitors or more." in text and "- Failed: linking pages of" in text


def test_an_unreadable_list_leaves_nothing_out_unsaid_and_offers_no_report(monkeypatch):
    world(monkeypatch)
    monkeypatch.setattr(competitors.blocklist, "load", lambda fresh=False: (_ for _ in ()).throw(OSError("HTTP Error 404")))
    r = competitors.competitors(OWN, [A, B], today=TODAY)
    assert r["new"][A]["rows"][0]["site"] == "farm.example" and r["networks"][0]["report"] == ""
    assert r["errors"] == ["spam list: HTTP Error 404; listed sites were not left out"]


def test_an_intersection_row_needs_two_rivals_and_folds_ranks_dates_and_spam():
    row = competitors.shared_row(both("x.example", {"1": 5, "3": 9}, spam=12), [A, B, C])
    assert row["rivals"] == [A, C] and row["rank"] == 9 and row["first_seen"] == "2026-09-01" and row["spam"] == 12
    assert competitors.shared_row(both("x.example", {"2": 5}), [A, B, C]) is None
    assert competitors.shared_row(both("x.example", {"1": 5, "7": 1}), [A, B]) is None     # a number past the rivals
    assert competitors.estimate(100) == 27600
    assert competitors.spellings(["a.example", "www.b.example"]) == ["a.example", "www.a.example", "www.b.example"]


def test_linking_pages_are_looked_up_past_the_rows_shown_one_call_per_rival(monkeypatch):
    monkeypatch.setattr(competitors, "LOOKED_UP", 3)
    rows = [{"site": f"s{i}.example", "hosts": [f"s{i}.example"], "rivals": [A]} for i in range(5)]
    shared = [{"site": "x.example", "hosts": ["x.example"], "rivals": [B, A]}]
    assert competitors.lookups({A: {"rows": rows}}, shared) == {A: ["s0.example", "s1.example", "s2.example"],
                                                               B: ["x.example"]}
