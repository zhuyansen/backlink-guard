"""No network: pages are strings, the paid sources are replaced."""
import base64
import io
import json
import re
import urllib.error
from datetime import date
from pathlib import Path

import pytest

from backlink_guard import find, history, ledger, page, placement, policy, profile, report, updates, verify, vet

TODAY = date(2026, 10, 13)
UPDATES = [{"name": "September 2026 spam update", "begin": "2026-09-24", "end": "2026-10-08"},
           {"name": "August 2026 spam update", "begin": "2026-08-18", "end": "2026-08-21"},
           {"name": "March 2026 core update", "begin": "2026-03-27", "end": "2026-04-08"}]


def months(values, scale=1000):
    return {f"2026-{i + 1:02d}-01": v * scale for i, v in enumerate(values)}


def read_of(text="", links="", dead=False, blocked=False, error="", extra=()):
    html = f"<html><title>T</title><body>{text}{links}</body></html>"
    home = {"url": "https://dir.example", "final": "https://dir.example/", "status": 200, "html": html,
            "error": error, "blocked": blocked, "dead": dead}
    parsed = page.parse("" if dead or blocked else html, home["final"])
    return {"home": home, "parsed": parsed, "texts": [parsed["text"], *extra]}


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKLINK_GUARD_STATE", str(tmp_path))
    for name in ("GOANYAPI_API_KEY", "AISA_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(vet.aisa, "key", lambda: "")


# ── reading a page ──────────────────────────────────────────────────────────

def test_parse_keeps_rel_and_skips_scripts():
    p = page.parse('<a href="/go" rel="NoFollow sponsored">Out</a><script>var a="<a href=x>";</script><p>Hello</p>',
                   "https://dir.example/x")
    assert p["links"] == [{"href": "https://dir.example/go", "rel": {"nofollow", "sponsored"}, "text": "Out", "placement": "unknown"}]
    assert "Hello" in p["text"] and "var a" not in p["text"]


def test_a_charset_python_does_not_know_reads_as_utf8(monkeypatch):
    class Headers:
        def get_content_charset(self):
            return "utf-8, text/xml"            # what one site sent on 2026-10-15

    class Response:
        status, headers = 200, Headers()

        def read(self, n):
            return "<title>Café</title>".encode()

        def geturl(self):
            return "https://odd.example/"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
    monkeypatch.setattr(page.urllib.request, "urlopen", lambda req, timeout: Response())
    got = page.fetch("odd.example")
    assert not got["dead"] and "Café" in got["html"]


def test_site_treats_subdomains_as_one_site():
    assert page.site("https://blog.example.co.uk/a") == "example.co.uk"
    assert page.site("www.launches.uicomet.com") == "uicomet.com"


def test_a_refused_request_is_not_a_dead_site(monkeypatch):
    def refuse(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 406, "Not Acceptable", {}, io.BytesIO(b""))
    monkeypatch.setattr(page.urllib.request, "urlopen", refuse)
    got = page.fetch("dev.to")          # dev.to answers 406 to a client it does not know
    assert got["blocked"] and not got["dead"]

    def gone(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b""))
    monkeypatch.setattr(page.urllib.request, "urlopen", gone)
    assert page.fetch("gone.example")["dead"]


# ── what a site says about itself ───────────────────────────────────────────

def test_a_free_tier_is_not_a_price():
    assert not vet.priced("Free $ 0 Get 3 dofollow links to boost your SEO", vet.SELLS)      # turbo0.com
    assert vet.priced("Review within 24 hours. Dofollow link (DR 71). $39", vet.SELLS)       # mcpservers.org
    assert vet.priced("Publishing Fee Structure: $50 review, $80.00 on acceptance", vet.SELLS)


def test_page_flags_name_what_was_seen():
    sells = vet.page_flags(read_of("Premium listing: dofollow backlink for $39 one-time."))
    assert [f["flag"] for f in sells] == ["paid_follow"] and "$39" in sells[0]["evidence"]
    swap = vet.page_flags(read_of("Free plan. Backlink to our site is required before review."))
    assert [f["flag"] for f in swap] == ["link_exchange"]
    parked = vet.page_flags(read_of("Website content is unavailable: the domain has expired. Renew your domain."))
    assert [f["flag"] for f in parked] == ["parked"]
    assert vet.page_flags(read_of(dead=True, error="NXDOMAIN"))[0]["flag"] == "dead"
    assert vet.page_flags(read_of(blocked=True, error="HTTP 403"))[0]["flag"] == "blocked"
    assert vet.page_flags(read_of("A directory of MCP servers. Submit yours.")) == []


def test_a_long_article_about_parked_domains_is_not_parked():
    text = "How to tell a parked domain: " + "words " * 800 + " this domain is parked"
    assert vet.page_flags(read_of(text)) == []


def test_the_price_note_reads_the_submit_pages_only():
    home_ad = read_of("Featured: SomeTool from $20/mo")                 # an advert on the home page
    assert vet.page_flags(home_ad) == []
    submit = read_of("Welcome", extra=["Submit your tool. Featured listing $29, live in 24 hours."])
    assert [f["flag"] for f in vet.page_flags(submit)] == ["paid_listing"]


def test_spam_neighbors_need_several_links():
    bad = "".join(f'<a href="https://casino{i}.example/">best online casino {i}</a>' for i in range(3))
    assert [f["flag"] for f in vet.page_flags(read_of(links=bad))] == ["spam_neighbors"]
    one = '<a href="https://casino.example/">casino night at the meetup</a>'
    assert vet.page_flags(read_of(links=one)) == []


# ── visits ──────────────────────────────────────────────────────────────────

def test_a_cliff_is_a_fall_within_a_month_that_did_not_come_back():
    creati = vet.visit_trend(months([604, 505, 552, 415, 334, 353, 321, 323, 167]))
    assert creati["cliff"] == ("2026-09", 0.52)
    flags = vet.traffic_flags(creati, 51, UPDATES)
    assert flags[0]["flag"] == "traffic_cliff" and "September 2026 spam update" in flags[0]["evidence"]
    recovered = vet.visit_trend(months([300, 300, 300, 300, 300, 300, 300, 150, 290]))
    assert recovered["cliff"] is None


def test_a_slow_decline_is_a_note_not_a_cliff():
    slow = vet.visit_trend(months([2133, 2177, 2156, 1963, 1531, 1449, 1402, 1100, 944, 900, 880, 860]))
    assert slow["cliff"] is None and [f["flag"] for f in vet.traffic_flags(slow, 72, UPDATES)] == ["traffic_decline"]
    assert policy.grade(vet.traffic_flags(slow, 72, UPDATES)) == "ok"


def test_a_high_rating_with_no_visitors_is_called_out():
    turbo = vet.visit_trend(months([5, 0, 14, 0, 0, 0, 2, 1, 2]))
    names = [f["flag"] for f in vet.traffic_flags(turbo, 81, UPDATES)]
    assert "hollow_rating" in names and "traffic_cliff" not in names      # 5,000 to nothing is below the level that counts


def test_updates_around_a_month():
    assert [u.split(" (")[0] for u in updates.around("2026-09", UPDATES)] == ["September 2026 spam update", "August 2026 spam update"]
    assert updates.around("2026-01", UPDATES) == []


# ── the whole check ─────────────────────────────────────────────────────────

def paid_world(monkeypatch, visits, dr=50, index=(10,), page_read=None, search=None, serp=None, pages=None):
    asked = []
    monkeypatch.setattr(vet.goanyapi, "key", lambda: "k")
    monkeypatch.setattr(vet.aisa, "key", lambda: "k")
    monkeypatch.setattr(vet, "read_site", lambda url: page_read or read_of("A directory."))
    monkeypatch.setattr(vet, "first_seen", lambda d: "2020-01-01")
    monkeypatch.setattr(vet, "pages_listed", lambda d: (pages or {}).get(d))
    monkeypatch.setattr(vet.updates, "ranking_updates", lambda: UPDATES)
    answers = iter(index)

    def goany(path, **params):
        asked.append(path)
        if path == "dr":
            return {"domain_rating": dr}, 2000
        if path == "traffic":
            return {"EstimatedMonthlyVisits": visits}, 4000
        return {"siteCount": next(answers), "organic": []}, 4000
    monkeypatch.setattr(vet.goanyapi, "call", goany)

    def aisa_call(tool, body):
        if tool == find.SERP_TOOL:
            return {"items": [{"type": "organic", "url": u, "title": t, "rank_absolute": n}
                              for u, t, n in (serp or {}).get(body["keyword"], [])]}, 5000
        if tool == find.VOLUME_TOOL:
            return {"items": [{"keyword": k, "keyword_info": {"search_volume": 1000}, "keyword_properties": {"keyword_difficulty": 20}}
                              for k in body["keywords"]]}, 12000
        if tool == history.TOOL:
            return {"items": [hist_item(t, *(search or {}).get(t, ([500] * 34,))) for t in body["targets"]]}, 130000
        return {"items": [{"target": t, "spam_score": 5} for t in body["targets"]]}, 25000
    monkeypatch.setattr(vet.aisa, "call", aisa_call)
    return asked


def hist_item(target, etv, count=None):
    """A DataForSEO history item, months from January 2024 on."""
    rows = [{"year": 2024 + i // 12, "month": i % 12 + 1, "etv": e, "count": c}
            for i, (e, c) in enumerate(zip(etv, count or [200] * len(etv)))]
    return {"target": target, "metrics": {"organic": rows}}


def month_keys(n):
    return [f"{2024 + i // 12}-{i % 12 + 1:02d}" for i in range(n)]


def test_a_site_people_visit_is_not_asked_about_its_index(monkeypatch):
    asked = paid_world(monkeypatch, months([300] * 12))
    row = vet.vet(["dir.example"], today=TODAY)["rows"][0]
    assert row["grade"] == "ok" and row["reach"] == "high" and "google-site-search" not in asked
    assert "indexed" not in row["metrics"]


def test_deindexed_needs_two_empty_answers(monkeypatch):
    asked = paid_world(monkeypatch, months([1] * 12), index=(0, 12))        # empty once, then twelve results
    row = vet.vet(["dir.example"], today=TODAY)["rows"][0]
    assert asked.count("google-site-search") == 2 and row["metrics"]["indexed"] == 12
    assert "deindexed" not in [f["flag"] for f in row["flags"]]
    paid_world(monkeypatch, months([1] * 12), index=(0, 0))
    again = vet.vet(["other.example"], today=TODAY, fresh=True)["rows"][0]
    assert again["grade"] == "avoid" and again["flags"][0]["flag"] == "deindexed"


def test_a_failed_request_to_a_busy_site_is_blocked_not_dead(monkeypatch):
    paid_world(monkeypatch, months([5000] * 12), page_read=read_of(dead=True, error="timed out"))
    row = vet.vet(["dev.example"], today=TODAY)["rows"][0]
    assert [f["flag"] for f in row["flags"]] == ["blocked"] and row["grade"] == "ok"


def test_paid_answers_are_bought_once(monkeypatch):
    asked = paid_world(monkeypatch, months([300] * 12))
    first = vet.vet(["dir.example"], today=TODAY)
    second = vet.vet(["dir.example"], today=TODAY)
    assert first["cost"] == 2000 + 4000 + 25000 + 130000 and second["cost"] == 0 and asked == ["dr", "traffic"]


# ── Google search history ───────────────────────────────────────────────────

FLAT = dict.fromkeys(month_keys(34), 1.0)


def test_a_fall_that_held_and_took_the_keywords_with_it_is_flagged():
    item = hist_item("dir.example", [1000] * 32 + [100] * 2, [500] * 32 + [50] * 2)     # falls in 2026-09
    metrics, found = history.flags_for(history.months(item), FLAT, TODAY, UPDATES)
    assert [f["flag"] for f in found] == ["search_fall"] and metrics["search_fall"] == "2026-09"
    assert "1,000 search visits a month before 2026-09, 100 after; ranking keywords 500 to 50" in found[0]["evidence"]
    assert "September 2026 spam update" in found[0]["evidence"] and "August 2026 spam update" in found[0]["evidence"]


def test_a_spike_that_drops_back_is_not_a_fall():
    # mcpmarket.com, 2026: 10 thousand to 3.4 million and back, keywords steady all along
    item = hist_item("spike.example", [50] * 20 + [5000] * 6 + [60] * 8, [300] * 34)
    assert history.falls(history.months(item), FLAT) == []


def test_a_fall_that_came_back_is_not_a_fall():
    item = hist_item("back.example", [1000] * 20 + [100] * 3 + [900] * 11, [500] * 20 + [50] * 3 + [450] * 11)
    assert history.falls(history.months(item), FLAT) == []


def test_a_shift_of_the_whole_database_is_not_a_fall():
    rebased = [1000] * 20 + [300] * 14                                       # every site at once
    data = {c: history.months(hist_item(c, rebased, [800] * 20 + [300] * 14)) for c in history.CONTROLS}
    data["dir.example"] = history.months(hist_item("dir.example", rebased, [500] * 20 + [200] * 14))
    assert history.falls(data["dir.example"], {}) != []                     # read raw, it looks like a fall
    assert history.falls(data["dir.example"], history.index(data)) == []


def test_an_old_fall_is_a_note_and_leaves_the_grade():
    item = hist_item("old.example", [1000] * 5 + [100] * 29, [500] * 5 + [50] * 29)      # 2024-06
    _, found = history.flags_for(history.months(item), FLAT, TODAY, UPDATES)
    assert [f["flag"] for f in found] == ["old_search_fall"] and policy.grade(found) == "ok"


def test_the_update_list_reaches_back_when_the_feed_is_short_or_down(monkeypatch):
    def down(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(updates.urllib.request, "urlopen", down)
    offline = updates.ranking_updates()
    assert len(offline) == len(updates.EARLIER) and offline[-1]["name"] == "November 2021 spam update"
    feed = [{"external_desc": "September 2026 spam update", "begin": "2026-09-24T16:15:00+00:00",
             "end": "2026-10-08T08:00:00+00:00", "affected_products": [{"title": "Ranking"}]}]
    monkeypatch.setattr(updates.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(json.dumps(feed).encode()))
    live = updates.ranking_updates()
    assert len(live) == len(updates.EARLIER) and live[0]["end"] == "2026-10-08"     # the feed's own end wins


def test_vet_adds_the_search_history(monkeypatch):
    paid_world(monkeypatch, months([300] * 12), search={"dir.example": ([1000] * 32 + [100] * 2, [500] * 32 + [50] * 2)})
    result = vet.vet(["dir.example"], today=TODAY)
    row = result["rows"][0]
    assert row["grade"] == "caution" and "search_fall" in [f["flag"] for f in row["flags"]]
    assert row["metrics"]["search_visits"] == 100 and result["cost"] == 2000 + 4000 + 25000 + 130000


def test_without_keys_the_page_checks_still_run(monkeypatch):
    monkeypatch.setattr(vet, "read_site", lambda url: read_of("Dofollow backlink for $39."))
    monkeypatch.setattr(vet, "first_seen", lambda d: "")
    result = vet.vet(["dir.example"], today=TODAY)
    assert result["rows"][0]["grade"] == "caution" and result["sources"] == {"goanyapi": False, "aisa": False, "free": False}
    from backlink_guard import report
    text = report.vet(result)
    assert "No `GOANYAPI_API_KEY`" in text and "not Google's judgment" in text
    asked_free = report.vet(vet.vet(["dir.example"], paid_sources=False, today=TODAY))
    assert "Run with `--free`" in asked_free and "No `GOANYAPI_API_KEY`" not in asked_free


# ── your own profile ────────────────────────────────────────────────────────

def weeks(*new):
    return [{"week": f"2026-{8 + i // 4:02d}-{1 + 7 * (i % 4):02d}", "new": n, "lost": 0} for i, n in enumerate(new)]


def test_velocity_compares_a_week_with_the_eight_before():
    assert profile.velocity(weeks(5, 6, 12, 10, 1, 6, 16, 8, 9)) is None
    spike = profile.velocity(weeks(5, 6, 12, 10, 1, 6, 16, 8, 40))
    assert spike["flag"] == "velocity_spike" and "40 new referring domains" in spike["evidence"]
    assert profile.velocity(weeks(0, 0, 0, 0, 0, 0, 0, 0, 4)) is None       # four links are not a spike


def test_anchor_kinds_and_the_repeat_flag():
    kinds = [profile.kind_of(a, "agentskillshub.top") for a in ("Agent Skills Hub", "agentskillshub.top", "Try Now", "", "MCP server directory")]
    assert kinds == ["brand", "url", "generic", "generic", "keyword"]
    assert profile.anchor_flag([("Agent Skills Hub", 40), ("best mcp directory", 30), ("", 30)], "agentskillshub.top")["flag"] == "anchor_repeat"
    assert profile.anchor_flag([("Agent Skills Hub", 90), ("best mcp directory", 10)], "agentskillshub.top") is None


def test_anchors_that_sell_links_are_reported():
    found = profile.spam_anchor_flag([("Agent Skills Hub", 1237), ("High Quality Dofollow Backlinks DA 50 PA 40 Premium PBN Network", 23)])
    assert found["flag"] == "spam_anchor" and "on 23 links" in found["evidence"]
    assert profile.spam_anchor_flag([("Agent Skills Hub", 5), ("database tools", 2)]) is None


def test_referrers_flag_needs_a_share():
    top = [{"site": s} for s in ("a.example", "b.example", "c.example", "d.example")]
    found, worst = profile.referrer_flag(top, {"a.example": 59, "b.example": 12, "c.example": 3, "d.example": 5})
    assert found["flag"] == "spammy_referrers" and worst == [{"site": "a.example", "spam_score": 59}]
    assert profile.referrer_flag(top + [{"site": f"{i}.example"} for i in range(8)], {"a.example": 59})[0] is None


# ── checking a listing ──────────────────────────────────────────────────────

def test_only_three_rel_values_hold_back_credit():
    link = lambda rel, href="https://agentskillshub.top/": {"href": href, "rel": set(rel.split()), "text": "Agent Skills Hub"}
    assert verify.classify(link("noopener external"), "agentskillshub.top", "dir.example")["passes_credit"]
    assert not verify.classify(link("nofollow noopener"), "agentskillshub.top", "dir.example")["passes_credit"]
    assert verify.classify(link("", "https://other.example/"), "agentskillshub.top", "dir.example") is None


def test_a_redirect_is_seen_even_when_encoded():
    token = base64.urlsafe_b64encode(b"https://agentskillshub.top/").decode().rstrip("=")
    hidden = verify.classify({"href": f"https://dir.example/go/?url={token}", "rel": set(), "text": "Open"}, "agentskillshub.top", "dir.example")
    assert hidden["how"] == "redirect" and not hidden["passes_credit"]


def test_verify_says_what_it_found(monkeypatch):
    html = '<a href="https://agentskillshub.top/" rel="ugc nofollow">Agent Skills Hub</a>'
    monkeypatch.setattr(page, "fetch", lambda url: {"url": url, "final": url, "status": 200, "html": html, "error": "", "blocked": False, "dead": False})
    assert verify.verify("https://dir.example/x", "agentskillshub.top")["verdict"] == "qualified link"
    monkeypatch.setattr(page, "fetch", lambda url: {"url": url, "final": url, "status": 200, "html": "<p>agentskillshub.top</p>", "error": "", "blocked": False, "dead": False})
    missing = verify.verify("https://dir.example/x", "agentskillshub.top")
    assert missing["verdict"] == "not found" and "script" in missing["note"]


# ── the record ──────────────────────────────────────────────────────────────

def test_ledger_flags_pace_and_a_repeated_anchor():
    for i in range(6):
        ledger.add(f"dir{i}.example", "directory", anchor="best mcp directory", today=TODAY)
    names = [f["flag"] for f in ledger.checks(ledger.entries(), today=TODAY)]
    assert names == ["pace", "anchor_repeat"]
    assert ledger.update("dir0.example", status="live", url="https://dir0.example/x")["status"] == "live"
    assert ledger.checks(ledger.entries()[:3], today=TODAY) == []           # three with one anchor: too few to judge


def test_grades():
    assert policy.grade([policy.flag("young", "x")]) == "ok"
    assert policy.grade([policy.flag("young", "x"), policy.flag("paid_follow", "y")]) == "caution"
    assert policy.grade([policy.flag("paid_follow", "y"), policy.flag("parked", "z")]) == "avoid"


def test_the_skill_names_the_commands_and_writes_no_dollar_amounts():
    text = (Path(__file__).resolve().parents[1] / "skills" / "backlink-guard" / "SKILL.md").read_text()
    head = re.match(r"---\nname: (\S+)\ndescription: (.+)\n---\n", text)
    assert head and head.group(1) == "backlink-guard" and 100 < len(head.group(2)) < 1024
    assert all(c in text for c in ("backlink_guard vet", "backlink_guard audit", "backlink_guard verify", "backlink_guard log"))
    assert not re.search(r"\$\d", text)        # Claude Code replaces $0, $1 ... in a skill with the user's arguments


# ── where a link sits ───────────────────────────────────────────────────────

PAGE = """<header><nav><a href="https://x.example/1">nav</a></nav></header>
<main><article class="post"><h1>T</h1><p>See <a href="https://x.example/2">this study</a>.
<div class="card"><a href="https://x.example/3">Visit</a></div>
<ul><li>item <a href="https://x.example/4">four</a></ul>
<div class="author-bio"><a href="https://x.example/5">me</a></div>
<div id="comments"><p><a href="https://x.example/6">spam</a></p></div></article>
<aside class="sidebar"><div class="widget"><a href="https://x.example/7">w</a></div></aside></main>
<footer class="site-footer"><p><a href="https://x.example/8">f</a></p></footer>
<div><a href="https://x.example/9">loose</a></div>"""


def test_placement_reads_the_elements_around_a_link():
    found = {l["href"][-1]: l["placement"] for l in page.parse(PAGE, "https://x.example/")["links"]}
    assert found == {"1": "navigation", "2": "body text", "3": "main area", "4": "body text", "5": "author box",
                     "6": "comments", "7": "sidebar", "8": "footer", "9": "unknown"}


def test_an_unclosed_paragraph_does_not_swallow_what_follows():
    # The <p> is never closed; the <div> that follows ends it, as browsers do.
    links = page.parse('<main><p>Intro text<div class="share"><a href="https://x.example/s">share</a></div></main>',
                       "https://x.example/")["links"]
    assert links[0]["placement"] == "main area"


def test_class_names_are_split_on_dashes_and_underscores():
    assert placement.region("div", "entry-content", "") == "content"
    assert placement.region("section", "widget_text", "") == "sidebar"
    assert placement.region("div", "authority-score", "") == ""          # "authority" is not "author"


def test_verify_says_when_no_followed_link_is_in_the_text(monkeypatch):
    html = '<article><p>Nothing here.</p></article><footer><a href="https://agentskillshub.top/">Agent Skills Hub</a></footer>'
    monkeypatch.setattr(page, "fetch", lambda url: {"url": url, "final": url, "status": 200, "html": html, "error": "", "blocked": False, "dead": False})
    result = verify.verify("https://dir.example/x", "agentskillshub.top")
    assert result["verdict"] == "followed link" and result["links"][0]["placement"] == "footer"
    assert "footers, templates and widgets" in result["note"]
    in_text = '<article><p>We used <a href="https://agentskillshub.top/">Agent Skills Hub</a> to check.</p></article>'
    monkeypatch.setattr(page, "fetch", lambda url: {"url": url, "final": url, "status": 200, "html": in_text, "error": "", "blocked": False, "dead": False})
    assert verify.verify("https://dir.example/x", "agentskillshub.top")["note"] == ""


# ── link networks, shorteners and lists (10-14: the top of a paid "backlink sources" list) ──

def titled(title):
    html = f"<html><title>{title}</title><body>Some text about the site.</body></html>"
    home = {"url": "https://x.example", "final": "https://x.example/", "status": 200, "html": html,
            "error": "", "blocked": False, "dead": False}
    parsed = page.parse(html, home["final"])
    return {"home": home, "parsed": parsed, "texts": [parsed["text"]]}


def test_shorteners_and_link_network_templates_are_avoided():
    assert [f["flag"] for f in vet.page_flags(titled("URL Shortener"))] == ["shortener"]
    assert [f["flag"] for f in vet.page_flags(titled("drjack.world | Keyword Rankingss"))] == ["link_farm"]
    assert [f["flag"] for f in vet.page_flags(titled("Free domain sharing - Site not yet configured"))] == ["link_farm"]
    assert vet.page_flags(titled("Rank Tracker: track your keyword rankings daily")) == []     # an SEO tool, not a template
    assert policy.grade(vet.page_flags(titled("URL Shortener"))) == "avoid"


def test_one_template_across_a_batch_is_called_a_network():
    rows = [{"domain": d, "title": t, "flags": []} for d, t in (
        ("drjack.world", "drjack.world | Keyword Rankingss"), ("quero.party", "quero.party | Keyword Rankingss"),
        ("glarity.app", "Glarity - Free ChatGPT YouTube Summary"), ("a.example", "Home"), ("b.example", "Home"))]
    vet.shared_templates(rows)
    assert [r["domain"] for r in rows if r["flags"]] == ["drjack.world", "quero.party"]
    assert "2 sites titled \"{site} | keyword rankingss\"" in rows[0]["flags"][0]["evidence"]


def test_a_rating_with_no_readers_is_hollow_from_30():
    trend = vet.visit_trend(months([1, 1, 1, 1, 1, 1, 1, 1, 1], scale=800))
    assert "hollow_rating" in [f["flag"] for f in vet.traffic_flags(trend, 45, UPDATES)]
    assert "hollow_rating" not in [f["flag"] for f in vet.traffic_flags(trend, 25, UPDATES)]


def test_lists_are_read_from_notes_csv_json_and_excel(tmp_path):
    from backlink_guard import lists
    note = "See gap.json and run fetch_backlinks.py. Targets: https://www.toolify.ai/x, mcp.so, Dev.to; mail me@x.example"
    assert lists.domains(note) == ["toolify.ai", "mcp.so", "dev.to"]
    import zipfile
    book = tmp_path / "list.xlsx"
    with zipfile.ZipFile(book, "w") as z:
        z.writestr("xl/sharedStrings.xml", "<sst><si><t>urls-shortener.eu</t></si><si><t>https://quero.party/</t></si></sst>")
        z.writestr("xl/worksheets/sheet1.xml", "<worksheet><row><c><v>0</v></c></row></worksheet>")
    assert lists.read(str(book)) == ["urls-shortener.eu", "quero.party"]


def test_targets_skip_and_limit(tmp_path, capsys):
    import argparse
    from backlink_guard import __main__ as cli
    listed = tmp_path / "gap.md"
    listed.write_text("apiflux.ai openrouter.ai robuta.com toolidx.com dev.to")
    have = tmp_path / "have.txt"
    have.write_text("dev.to")
    args = argparse.Namespace(targets=["saashub.com"], from_file=str(listed), skip=["apiflux.ai", "openrouter.ai", str(have)], limit=2)
    assert cli.targets_of(args) == ["saashub.com", "robuta.com"]
    assert "3 sites found; checking the first 2" in capsys.readouterr().err      # saashub, robuta, toolidx


# ── recent indexing (10-14: a "no page indexed in 30 days" verdict that did not reproduce) ──

def test_a_failed_search_is_not_a_zero(monkeypatch):
    monkeypatch.setattr(vet.goanyapi, "call", lambda path, **p: (_ for _ in ()).throw(vet.goanyapi.GoAnyError("timed out")))
    metrics, flags, cost, errors = vet.recent_flags("dir.example", TODAY, False)
    assert flags == [] and "indexed_month" not in metrics and len(errors) == 2


def test_no_recent_pages_needs_two_zeros_and_an_active_sitemap(monkeypatch):
    answers = {"w": iter([0, 0]), "m": iter([0, 0])}
    monkeypatch.setattr(vet.goanyapi, "call", lambda path, site, qdr: ({"siteCount": next(answers[qdr]), "organic": []}, 4000))
    monkeypatch.setattr(vet, "site_activity", lambda domain, today: 120)
    metrics, flags, cost, _ = vet.recent_flags("dir.example", TODAY, False)
    assert [f["flag"] for f in flags] == ["not_indexing"] and "120 pages" in flags[0]["evidence"] and cost == 16000

    answers = {"w": iter([0, 0]), "m": iter([0, 0])}
    monkeypatch.setattr(vet, "site_activity", lambda domain, today: 0)
    _, quiet, _, _ = vet.recent_flags("quiet.example", TODAY, True)
    assert [f["flag"] for f in quiet] == ["inactive"] and policy.grade(quiet) == "ok"


def test_a_second_look_can_find_pages(monkeypatch):
    answers = {"w": iter([0, 9]), "m": iter([25])}

    def search(path, site, qdr):
        n = next(answers[qdr])
        return {"siteCount": n, "organic": [{"extensions": [{"text": "20 hours ago"}]}] if n else []}, 4000
    monkeypatch.setattr(vet.goanyapi, "call", search)
    metrics, flags, _, _ = vet.recent_flags("findly.example", TODAY, True)
    assert flags == [] and metrics["indexed_week"] == 9 and metrics["indexed_month"] == 25 and metrics["newest_indexed"] == "20 hours ago"


def test_sitemap_activity_counts_recent_lastmod(monkeypatch):
    pages = {"https://s.example/robots.txt": "User-agent: *\nSitemap: https://s.example/index.xml\n",
             "https://s.example/index.xml": "<sitemapindex><sitemap><loc>https://s.example/a.xml</loc></sitemap></sitemapindex>",
             "https://s.example/a.xml": "<urlset><url><lastmod>2026-10-10</lastmod></url><url><lastmod>2026-09-20</lastmod></url>"
                                         "<url><lastmod>2026-08-01</lastmod></url></urlset>"}
    monkeypatch.setattr(page, "fetch", lambda url: {"url": url, "final": url, "status": 200, "html": pages.get(url, ""),
                                                    "error": "", "blocked": False, "dead": url not in pages})
    assert vet.site_activity("s.example", TODAY) == 2
    monkeypatch.setattr(page, "fetch", lambda url: {"url": url, "final": url, "status": 404, "html": "", "error": "HTTP 404", "blocked": False, "dead": True})
    assert vet.site_activity("none.example", TODAY) is None


# ── badge networks, unproven sites, link sellers (10-14: Ahrefs' SPAM mark on 90 referring domains) ──

def test_badge_network_and_unproven_from_the_link_profile():
    badge = {"referring_domains": 200, "links_per_domain": 630.0, "template_link_share": 0.76,
             "nofollow_domain_share": 0.08, "indexed_since": "2025-07-29"}
    assert [f["flag"] for f in vet.profile_flags(badge, TODAY)] == ["badge_network"]
    editorial = {**badge, "links_per_domain": 9.5, "template_link_share": 0.03}          # links in articles, a few each
    assert vet.profile_flags(editorial, TODAY) == []
    new = {"referring_domains": 12, "links_per_domain": 1.4, "template_link_share": 0.0,
           "nofollow_domain_share": 0.1, "indexed_since": "2026-05-01"}
    assert [f["flag"] for f in vet.profile_flags(new, TODAY)] == ["unproven"]
    old_small = {**new, "indexed_since": "2019-01-01"}
    assert vet.profile_flags(old_small, TODAY) == []


def test_deep_reads_the_profile_and_spares_a_site_people_visit(monkeypatch):
    paid_world(monkeypatch, months([300] * 12))
    summary = {"referring_domains": 12, "backlinks": 20, "referring_domains_nofollow": 1, "first_seen": "2026-05-01 00:00:00 +00:00",
               "referring_links_semantic_locations": {"main": 10}}
    calls = []
    def router(tool, body):
        calls.append(tool)
        if tool == vet.SUMMARY_TOOL:
            return summary, 24000
        return {"items": [{"target": t, "spam_score": 5} for t in body["targets"]]}, 25000
    monkeypatch.setattr(vet.aisa, "call", router)
    busy = vet.vet(["dir.example"], today=TODAY, deep=True)["rows"][0]
    assert vet.SUMMARY_TOOL in calls and "unproven" not in [f["flag"] for f in busy["flags"]]     # 300K visits a month
    paid_world(monkeypatch, months([0.1] * 12))
    monkeypatch.setattr(vet.aisa, "call", router)
    quiet = vet.vet(["quiet.example"], today=TODAY, deep=True, fresh=True)["rows"][0]
    assert "unproven" in [f["flag"] for f in quiet["flags"]] and quiet["metrics"]["referring_domains"] == 12


def test_link_sellers_and_badge_requirements_read_from_the_page():
    assert [f["flag"] for f in vet.page_flags(titled("LinkBuildSEO.com — Premium DR, DA, TF, PBN & Guest Posts"))] == ["link_seller"]
    assert vet.EXCHANGE.search("Mandatory Badge: You must place our badge on your site permanently")
    assert vet.EXCHANGE.search("Start with Free Listing if you are happy to add a Navai backlink first.")
    assert not vet.EXCHANGE.search("PRO Member Extra Features Display a PRO badge next to your username")       # v2ex
    assert not vet.page_flags(titled("Discover Startup Launches from all over the web, Everyday - StartupTile"))


# ── where your searches land (find) ─────────────────────────────────────────

SERP = {"claude skills": [
    ("https://platform.claude.com/docs/en/agent-skills/overview", "Agent Skills - Claude Platform Docs", 1),
    ("https://github.com/someone/awesome-claude-skills", "awesome-claude-skills: a curated list", 2),
    ("https://agentskillshub.top/best/claude-skills/", "Claude skills, reviewed", 3),
    ("https://skilldir.example/", "Skill Directory - every Claude skill", 4),
    ("https://blog.example/posts/the-10-claude-skills/", "The 10 Claude Skills I Use", 5),
    ("https://writer.example/what-is-a-claude-skill", "What Is a Claude Skill?", 12),
    ("https://www.youtube.com/watch?v=x", "Claude Skills tutorial", 14),
    ("https://acme.example/", "Acme - build skills for Claude", 25)]}


def test_kinds_of_pages():
    assert [find.kind_of(u, t) for u, t, _ in SERP["claude skills"]] == [
        "docs", "list", "list", "directory", "list", "article", "video", "site"]
    assert find.kind_of("https://www.reddit.com/r/ClaudeAI/comments/1/x/", "What are skills?") == "community"
    assert find.kind_of("https://skillsllm.com/skill/education-skills", "education-skills") == "directory"
    assert find.kind_of("https://github.com/onewave/claude-skills", "200+ skills") == "repo"
    assert find.kind_of("https://www.mdskills.ai/skills/game-studios", "Game Studios — 36 Skills") == "directory"
    assert find.kind_of("https://www.claudefluent.com/skills", "Skills Explorer") == "directory"
    assert find.kind_of("https://www.firecrawl.dev/blog/best-claude-code-skills", "14 Best Claude Code Skills") == "list"
    assert find.kind_of("https://github.com/topics/agent-skills", "agent-skills · GitHub Topics") == "directory"


def test_find_sorts_by_visitors_and_leaves_out_your_site(monkeypatch):
    paid_world(monkeypatch, months([300] * 12), serp=SERP)
    result = find.find(["claude skills"], own="agentskillshub.top")
    urls = [p["url"] for p in result["pages"]]
    assert not any("agentskillshub.top" in u for u in urls)
    assert urls[0] == "https://github.com/someone/awesome-claude-skills" and result["pages"][0]["visitors"] == 158
    assert [p["kind"] for p in result["pages"]][-2:] == ["docs", "site"]          # not sources: last
    assert result["cost"] == 5000 + 12000 and result["keywords"]["claude skills"]["volume"] == 1000
    assert find.to_vet(result, 10) == ["skilldir.example", "blog.example", "writer.example"]   # platforms left out
    text = report.find(result)
    assert "| about 158 |" in text and "Not link sources" in text and "rel=\"sponsored\"" in text


def test_vet_shows_where_a_site_ranks_for_your_topic(monkeypatch):
    paid_world(monkeypatch, months([300] * 12), serp=SERP, page_read=read_of("Every Claude skill, sorted."))
    result = vet.vet(["skilldir.example", "other.example"], today=TODAY, topics=("claude skills",))
    fit = {r["domain"]: r["metrics"].get("fit") for r in result["rows"]}
    assert fit["skilldir.example"]["position"] == 4 and fit["other.example"] is None
    assert all(r["metrics"]["mentions"] for r in result["rows"])        # both pages carry "claude" and "skills"
    text = report.vet(result)
    assert "| Fit |" in text and "#4 for \u201cclaude skills\u201d" in text and "writes about it" in text


# ── many pages, no rankings (scaled_pages) ───────────────────────────────────

def test_pages_listed_reads_the_index_and_extrapolates(monkeypatch):
    def fetch(url):
        if url.endswith("robots.txt"):
            body = "Sitemap: https://farm.example/sitemap_index.xml"
        elif url.endswith("sitemap_index.xml"):
            body = "<sitemapindex>" + "".join(f"<sitemap><loc>https://farm.example/s{i}.xml</loc></sitemap>" for i in range(10)) + "</sitemapindex>"
        else:
            body = "<urlset>" + "<url><loc>https://farm.example/p</loc></url>" * 500 + "</urlset>"
        return {"html": body, "dead": False, "blocked": False}
    monkeypatch.setattr(vet.page, "fetch", fetch)
    assert vet.pages_listed("farm.example") == 5000          # six files read, four more at their average
    monkeypatch.setattr(vet.page, "fetch", lambda url: (_ for _ in ()).throw(AssertionError("read twice")))
    assert vet.pages_listed("farm.example") == 5000          # kept for a week


def test_thousands_of_pages_and_no_rankings_is_flagged_in_english_only():
    assert [f["flag"] for f in history.scaled(105021, 2, "en-us")] == ["scaled_pages"]
    assert history.scaled(105021, 2, "it") == []               # Italian site: US rankings say little
    assert history.scaled(800, 0, None) == [] and history.scaled(146670, 219, None) == []   # too few pages; 670 a keyword
    assert "about 52,510 pages for each" in history.scaled(105021, 2, None)[0]["evidence"]


def test_vet_weighs_pages_against_rankings(monkeypatch):
    paid_world(monkeypatch, months([300] * 12), pages={"farm.example": 43680},
               search={"farm.example": ([0] * 34, [0] * 34)})
    row = vet.vet(["farm.example"], today=TODAY)["rows"][0]
    assert "scaled_pages" in [f["flag"] for f in row["flags"]] and row["metrics"]["ranking_keywords"] == 0
