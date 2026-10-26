"""cited: the sites Google's AI Overview cites for your keywords. AIsa is stubbed: no network."""
from backlink_guard import cited, report

OWN = "mine.example"


def reference(url, title, source=""):
    return {"type": "ai_overview_reference", "source": source, "domain": url.split("/")[2], "url": url, "title": title}


OVERVIEW = {"type": "ai_overview", "asynchronous_ai_overview": False, "markdown": "Skills are packages [[1]](...)",
            "items": [{"type": "ai_overview_element", "title": "How skills work", "text": "...",
                       "references": [reference("https://docs.tool-a.example/skills", "What are skills", "Docs"),
                                      reference("https://mine.example/best/skills/", "Skills, reviewed")],
                       "links": [{"type": "link_element", "url": "https://list.example/best-skills", "title": "The 12 best skills"}],
                       "images": [{"type": "images_element", "url": "https://img.example/x.png", "alt": "a picture"}]}],
            "references": [reference("https://docs.tool-a.example/skills", "What are skills", "Docs"),
                           reference("https://www.youtube.com/watch?v=abc", "Skills explained", "YouTube")]}
SERPS = {
    "agent skills": {"items": [OVERVIEW, {"type": "organic", "rank_group": 1, "url": "https://docs.tool-a.example/skills"},
                               {"type": "organic", "rank_group": 4, "url": "https://www.mine.example/best/skills/"}]},
    "skill directory": {"items": [{"type": "organic", "rank_group": 2, "url": "https://list.example/directories"}]},
    "claude skills": {"items": [{"type": "knowledge_graph", "items": [{
        "type": "knowledge_graph_ai_overview_item", "items": [], "references": [
            reference("https://list.example/best-skills", "The 12 best skills"),
            reference("https://forum.example/t/skills", "Which skills do you use?")]}]}]},
}


def world(monkeypatch, cost=2000):
    calls = []

    def call(tool, body):
        calls.append(body)
        assert tool == cited.TOOL and body["load_async_ai_overview"] is True and body["depth"] == 10
        return SERPS[body["keyword"]], cost
    monkeypatch.setattr(cited.aisa, "call", call)
    return calls


def test_citations_are_the_references_and_links_each_page_once():
    found = cited.citations(OVERVIEW)
    assert [c["url"] for c in found] == ["https://docs.tool-a.example/skills", "https://mine.example/best/skills/",
                                         "https://list.example/best-skills", "https://www.youtube.com/watch?v=abc"]
    assert found[0]["site"] == "tool-a.example" and found[0]["title"] == "What are skills"   # images are not citations


def test_each_keyword_says_whether_there_is_an_overview_and_whether_it_cites_you(monkeypatch):
    calls = world(monkeypatch)
    c = cited.cited("www.mine.example", ["agent skills", "skill directory", "claude skills", " agent  skills "])
    rows = {r["keyword"]: r for r in c["keywords"]}
    assert len(calls) == 3 and c["cost"] == 6000 and c["domain"] == OWN                    # the repeat asked once
    assert rows["agent skills"]["you"] == ["https://mine.example/best/skills/"] and rows["agent skills"]["rank"] == 4
    assert rows["skill directory"]["overview"] is False and rows["skill directory"]["cited"] == []
    assert rows["claude skills"]["overview"] and [x["site"] for x in rows["claude skills"]["cited"]] == ["list.example", "forum.example"]
    assert [(s["site"], len(s["keywords"]), s["citations"]) for s in c["sites"][:2]] == [("list.example", 2, 2), ("forum.example", 1, 1)]
    assert next(s for s in c["sites"] if s["site"] == OWN)["you"] and c["sites"][0]["kind"] == "list"


def test_the_report_says_no_overview_plainly_and_lists_the_places_to_be_mentioned(monkeypatch):
    world(monkeypatch)
    text = report.cited(cited.cited(OWN, ["agent skills", "skill directory", "claude skills"]))
    assert "| agent skills | yes | 4 | ✅ cited: /best/skills/ | #4 |" in text
    assert "| skill directory | no AI Overview | – | – | not in the top 10 |" in text
    assert "| claude skills | yes | 2 | not cited | not in the top 10 |" in text
    assert "| list.example | 2 | 2 | [The 12 best skills](https://list.example/best-skills) | list |" in text
    assert "| mine.example (you) | 1 | 1 |" in text and "- list: Ask to be added" in text
    assert "Cost of this run: $0.006 (cap $0.10)." in text


def test_the_cap_and_the_cache(monkeypatch):
    calls = world(monkeypatch)
    capped = cited.cited(OWN, ["agent skills", "skill directory", "claude skills"], max_usd=0.007)    # two cost $0.004
    assert len(calls) == 2 and capped["left_out"] == ["“claude skills”"]
    assert "**Not asked, over the cap of $0.01:** “claude skills”" in report.cited(capped)
    calls = world(monkeypatch)
    again = cited.cited(OWN, ["agent skills", "skill directory"], max_usd=0)
    assert calls == [] and again["cost"] == 0 and len(again["keywords"]) == 2


def test_a_failed_keyword_is_reported_and_the_rest_go_on(monkeypatch):
    world(monkeypatch)
    plain = cited.aisa.call

    def call(tool, body):
        if body["keyword"] == "claude skills":
            raise cited.aisa.AisaError("Internal SE Server Error.")
        return plain(tool, body)
    monkeypatch.setattr(cited.aisa, "call", call)
    c = cited.cited(OWN, ["claude skills", "agent skills"])
    assert c["errors"] == ["“claude skills”: Internal SE Server Error."] and [r["keyword"] for r in c["keywords"]] == ["agent skills"]
