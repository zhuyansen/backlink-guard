"""asked and questions: what AI assistants answer for your questions. AIsa is stubbed: no network."""
import threading
import time
from collections import Counter

import pytest

from backlink_guard import __main__ as cli
from backlink_guard import asked, cache, report
from backlink_guard.budget import Budget, OverBudget

OWN = "mine.example"
Q1, Q2 = "where can I find agent skills?", "best directory for claude skills"
REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AbC"


def llm(text, notes, fan_out=None):
    return {"fan_out_queries": fan_out, "items": [{"type": "message", "sections": [
        {"type": "text", "text": text, "annotations": [{"title": t, "url": u} for t, u in notes]}]}]}


ANSWERS = {
    "chatgpt": {"markdown": "**My top pick is [Mine](https://mine.example/)**, then a list.", "brand_entities": [],
                "fan_out_queries": ["agent skills directory 2026", "Agent  Skills directory 2026"],
                "sources": [{"url": "https://list.example/best-skills", "title": "The 12 best skills", "domain": "list.example"},
                            {"url": "https://mine.example/", "title": "Mine", "domain": "mine.example"}],
                "search_results": [{"url": "https://forum.example/t/skills", "title": "Which skills?", "domain": "forum.example"}]},
    "ai_mode": {"items": [{"type": "ai_overview", "references": [],
                           "markdown": "Top results: [](https://www.reddit.com/r/x/comments/1/best/) ![](https://cdn.example/i.png) "
                                       "[The 12 best skills](https://list.example/best-skills)"}]},
    "perplexity": llm("1. **Tool A** - good\n2. **Mine** - also good", [("The 12 best skills", "https://list.example/best-skills")]),
    "claude": llm("Start with the official repo.", [("Skills docs", "https://docs.tool-a.example/skills")],
                  ["agent skills directory 2026", "claude skills marketplace"]),
    "gemini": llm("Several directories exist.", [("reddit.com", REDIRECT), ("list.example", REDIRECT)], ["where to find skills"]),
}
COST = {"chatgpt": 4000, "ai_mode": 4000, "perplexity": 5800, "claude": 47000, "gemini": 45000}


def world(monkeypatch, delay=0.0):
    calls = []

    def rest(path, body):
        engine = next(e for e, x in asked.ENGINES.items() if x["path"] == path)
        calls.append((engine, body))
        time.sleep(delay)
        return ANSWERS[engine], COST[engine]
    monkeypatch.setattr(asked.aisa, "rest", rest)
    return calls


def test_each_engine_is_read_its_own_way():
    c = asked.read_scraper(ANSWERS["chatgpt"])
    assert [p["site"] for p in c["cited"]] == ["list.example", "mine.example"] and c["read"][0]["site"] == "forum.example"
    m = asked.read_serp(ANSWERS["ai_mode"])
    assert [p["url"] for p in m["cited"]] == ["https://www.reddit.com/r/x/comments/1/best/", "https://list.example/best-skills"]
    g = asked.read_llm(ANSWERS["gemini"])        # Gemini's redirect: the site its title names, no page
    assert [(p["site"], p["url"]) for p in g["cited"]] == [("reddit.com", ""), ("list.example", "")]
    assert asked.read_llm(ANSWERS["perplexity"])["names"] == ["Tool A", "Mine"]


def test_you_are_named_by_domain_or_by_name_and_short_labels_do_not_count():
    assert asked.named_how("Try Agent Skills Hub today", "agentskillshub.top", []) == "name"
    assert asked.named_how("see mine.example", OWN, []) == "domain" and asked.named_how("Mine Co is good", OWN, ["Mine Co"]) == "name"
    assert asked.named_how("skills everywhere", "skills.sh", []) == ""        # "skills" is in every answer


def test_a_site_of_the_same_name_takes_the_name_but_never_your_domain():
    # 2026-10-21: Perplexity's "AgentSkillsHub" was agentskillshub.dev, a directory under the same name
    own, text = "agentskillshub.top", "AgentSkillsHub reviews skills before install (agentskillshub.dev)."
    others = asked.lookalikes(own, ["github.com"], text)
    assert others == {"agentskillshub.dev"} and asked.named_how(text, own, ["Agent Skills Hub"], others) == ""
    assert asked.named_how(text + " See also agentskillshub.top.", own, [], others) == "domain"
    assert asked.lookalikes("mine.example", ["mine.dev"]) == set()           # a short name is too common to match on
    row = asked.site_row("agentskillshub.dev", {"answers": 2, "engines": {"claude"}, "questions": {Q1},
                                                "pages": {"https://agentskillshub.dev/": "Agent Skills Directory"}}, own)
    assert row["lookalike"] and not row["you"]


def test_an_answer_per_engine_and_sample_and_the_tally(monkeypatch):
    calls = world(monkeypatch)
    a = asked.asked("www.mine.example", [Q1, Q2, " " + Q1], names=["Mine"])
    assert len(calls) == 2 * 7 and a["questions"] == [Q1, Q2]            # ChatGPT and Perplexity twice, the repeat once
    assert sorted(b["web_search"] for e, b in calls if e in ("claude", "gemini")) == [True] * 4
    assert all("web_search" not in b for e, b in calls if e == "perplexity") and a["cost"] == 2 * 115600
    eng = {e["engine"]: e for e in a["by_engine"]}
    assert (eng["chatgpt"]["answers"], eng["chatgpt"]["named_you"], eng["chatgpt"]["cited_you"]) == (4, 4, 4)
    assert (eng["claude"]["named_you"], eng["claude"]["cited_you"], eng["claude"]["searches"]) == (0, 0, 2.0)
    assert (eng["perplexity"]["named_you"], eng["perplexity"]["name_only"]) == (0, 4)   # "Mine", a bold name, no domain
    # as many answers, more assistants first: reddit (AI Mode and Gemini) before you (ChatGPT only)
    assert [(s["site"], s["answers"]) for s in a["sites"][:3]] == [("list.example", 12), ("reddit.com", 4), ("mine.example", 4)]
    assert a["sites"][0]["kind"] == "list" and a["sites"][1]["kind"] == "community" and a["sites"][2]["you"]
    assert a["pages"][0]["url"] == "https://list.example/best-skills" and a["pages"][0]["engines"] == ["ai_mode", "chatgpt", "perplexity"]
    assert a["searches"][0] == {"query": "agent skills directory 2026", "times": 10, "engines": ["chatgpt", "claude"]}


def test_the_cap_leaves_out_whole_answers_and_says_so(monkeypatch):
    calls = world(monkeypatch)
    a = asked.asked(OWN, [Q1], engines=["chatgpt", "claude"], max_usd=0.07)     # 2 x 0.004 + 0.06 fits, no more
    assert len(calls) == 3 and a["left_out"] == [] and a["cost"] == 55000
    calls = world(monkeypatch)
    b = asked.asked(OWN, [Q2], engines=["chatgpt", "claude"], max_usd=0.05)
    assert [e for e, _ in calls] == ["chatgpt", "chatgpt"] and b["left_out"] == [f"claude “{Q2}”"]
    assert "**Not asked, over the cap of $0.05:** claude" in report.asked(b)


def test_calls_side_by_side_hold_their_estimates_against_the_cap(monkeypatch):
    budget, started, out = Budget(0.010), threading.Barrier(2), []

    def fetch():
        time.sleep(0.05)
        return {"ok": 1}, 6000

    def one(key):
        started.wait()
        try:
            out.append(budget.ask(key, 6000, fetch)[1])
        except OverBudget:
            out.append("left out")
    threads = [threading.Thread(target=one, args=(k,)) for k in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(map(str, out)) == ["6000", "left out"] and budget.spent == 6000 and budget.held == 0


def test_a_returned_call_counts_as_spent_ahead_of_caching_its_answer(monkeypatch):
    """Up to 0.11.1 a call that returned gave its estimate back, wrote its answer to the cache and only then counted
    what it cost: a call asked in that gap saw room that was already spent. Here the first call is held there."""
    budget, writing, go_on, put = Budget(0.006), threading.Event(), threading.Event(), cache.put

    def held_put(key, value):
        if key == "first":
            writing.set()
            go_on.wait(5)
        put(key, value)
    monkeypatch.setattr(cache, "put", held_put)
    first = threading.Thread(target=budget.ask, args=("first", 6000, lambda: ({"ok": 1}, 6000)))
    first.start()
    assert writing.wait(5)
    try:
        budget.ask("second", 6000, lambda: ({"ok": 2}, 6000))
        second = "asked"
    except OverBudget:
        second = "left out"
    go_on.set()
    first.join()
    assert second == "left out" and budget.spent == 6000 and budget.held == 0 and budget.left_out == ["second"]


def test_a_failed_call_gives_its_estimate_back_and_costs_nothing():
    budget = Budget(0.006)

    def down():
        raise asked.aisa.AisaError("call failed")
    with pytest.raises(asked.aisa.AisaError):
        budget.ask("first", 6000, down)
    assert (budget.spent, budget.held) == (0, 0) and budget.ask("second", 6000, lambda: ({"ok": 2}, 6000))[1] == 6000


def test_the_report(monkeypatch):
    world(monkeypatch)
    text = report.asked(asked.asked(OWN, [Q1], names=["Mine"]))
    assert "| chatgpt | 2 | 2 | 0 | 2 | 0 | 2.0 | 2.0 |" in text and "| ai_mode | 1 | 0 | 0 | 0 | 0 | – | 2.0 |" in text
    assert "| perplexity | 2 | 0 | 2 | 0 | 0 |" in text
    assert "| list.example | 6 | ai_mode, chatgpt, gemini, perplexity | 1 | [The 12 best skills](https://list.example/best-skills) | list |" in text
    assert "## Pages cited in two answers or more" in text and "- agent skills directory 2026 (×5: chatgpt, claude)" in text
    assert "Tool A ×2" in text and "Mine (you) ×2" in text and "Cost of this run: $0.116 (cap $1.00)." in text


SEARCHES = ["agent skills directory 2026", "claude skills marketplace", "where to find skills"]   # the most run first
RESULTS = {
    ("google", SEARCHES[0]): ["https://list.example/best-skills", "https://www.mine.example/skills", "https://forum.example/t/1"],
    ("bing", SEARCHES[0]): ["https://forum.example/t/1", "https://list.example/best-skills"],
    ("google", SEARCHES[1]): ["https://list.example/best-skills"] + [f"https://site{n}.example/" for n in range(9)]
                             + ["https://mine.example/"],
    ("bing", SEARCHES[1]): ["https://docs.tool-a.example/skills"],
    ("google", SEARCHES[2]): ["https://list.example/best-skills"],
    ("bing", SEARCHES[2]): [],
}


def ranking(monkeypatch, fail=None):
    """The world above, plus Google's and Bing's results for the searches; `fail` {(engine, search): times} raises
    the server error AIsa passes on that many times first."""
    calls, answering, tries = world(monkeypatch), asked.aisa.rest, Counter()

    def rest(path, body):
        engine = next((e for e, p in asked.RANK_PATHS.items() if p == path), None)
        if engine is None:
            return answering(path, body)
        tries[(engine, body["keyword"])] += 1
        if tries[(engine, body["keyword"])] <= (fail or {}).get((engine, body["keyword"]), 0):
            raise asked.aisa.AisaError("Internal SE Server Error.")
        calls.append((engine, body))
        items = [{"type": "paid", "url": "https://ad.example/"}] + [
            {"type": "organic", "url": u, "rank_group": n} for n, u in enumerate(RESULTS[(engine, body["keyword"])], 1)]
        return {"items": items}, 3500
    monkeypatch.setattr(asked.aisa, "rest", rest)
    return calls, tries


def test_each_search_they_ran_is_looked_up_on_google_and_bing(monkeypatch):
    calls, _ = ranking(monkeypatch)
    a = asked.asked(OWN, [Q1], rank=True)
    looked = [(e, b["keyword"]) for e, b in calls if e in asked.RANK_PATHS]
    assert sorted(looked) == sorted((e, q) for q in SEARCHES for e in asked.RANK_PATHS)
    assert all(b["depth"] == 20 and b["location_code"] == 2840 for e, b in calls if e in asked.RANK_PATHS)
    r = a["ranks"]
    assert [x["query"] for x in r["searches"]] == SEARCHES and r["searches"][0]["assistants"] == ["chatgpt", "claude"]
    first = r["searches"][0]["google"]
    assert (first["you"], first["your_page"], first["first_page"]) == (
        2, "https://www.mine.example/skills", ["list.example", "mine.example", "forum.example"])
    assert r["searches"][1]["google"]["you"] == 11 and "mine.example" not in r["searches"][1]["google"]["first_page"]
    eng = {e["engine"]: e for e in r["by_engine"]}
    assert (eng["google"]["searches"], eng["google"]["you"], eng["google"]["you_first_page"]) == (3, 2, 1)
    assert (eng["bing"]["you"], eng["bing"]["failed"], eng["bing"]["left_out"]) == (0, 0, 0)
    # ranks for all three and cited in six answers; the forum ranks twice and no answer cited it
    assert (r["sites"][0]["site"], r["sites"][0]["google"], r["sites"][0]["bing"], r["sites"][0]["cited"]) == (
        "list.example", 3, 1, 6)
    assert next(s for s in r["sites"] if s["site"] == "forum.example")["cited"] == 0
    assert r["cost"] == 6 * 3500 and a["cost"] == 115600 + 6 * 3500


def test_a_site_under_your_name_is_told_apart_in_the_results():
    rows = asked.organic({"items": [{"type": "paid", "url": "https://ad.example/"},
                                    {"type": "organic", "url": "https://skillshelf.dev/", "rank_group": 1},
                                    {"type": "organic", "url": "https://www.skillshelf.example/x", "rank_group": 2}]})
    p = asked.placed(rows, "skillshelf.example")
    assert (p["you"], p["lookalike"], p["lookalike_site"]) == (2, 1, "skillshelf.dev")


def test_a_failed_search_is_asked_again_and_two_failures_count_as_failed(monkeypatch):
    _, tries = ranking(monkeypatch, fail={("google", SEARCHES[1]): 1, ("bing", SEARCHES[2]): 2})
    a = asked.asked(OWN, [Q1], rank=True)
    r = a["ranks"]
    assert tries[("google", SEARCHES[1])] == 2 and r["searches"][1]["google"]["you"] == 11
    assert tries[("bing", SEARCHES[2])] == 2 and r["searches"][2]["bing"] == {"error": "Internal SE Server Error."}
    eng = {e["engine"]: e for e in r["by_engine"]}
    assert (eng["bing"]["searches"], eng["bing"]["failed"]) == (2, 1)
    text = report.asked(a)
    assert "**Failed twice, not read as missing:** “Internal SE Server Error.” ×1" in text
    assert "| bing | 2 | 0 | 0 | 0 | 1 | 0 |" in text and "Bing failed" not in text


def test_the_cap_leaves_out_the_rarest_searches_and_cached_answers_cost_nothing(monkeypatch):
    calls, _ = ranking(monkeypatch)
    asked.asked(OWN, [Q1])                                         # the answers, now in the cache
    monkeypatch.setattr(asked, "WORKERS", 1)
    calls.clear()
    a = asked.asked(OWN, [Q1], rank=True, max_usd=0.01)            # two lookups at $0.0035 fit, a third does not
    assert [(e, b["keyword"]) for e, b in calls] == [("google", SEARCHES[0]), ("bing", SEARCHES[0])]
    assert a["left_out"] == [] and len(a["ranks"]["left_out"]) == 4 and a["cost"] == 7000
    assert [e["left_out"] for e in a["ranks"]["by_engine"]] == [2, 2]
    assert "**Not looked up, over the cap of $0.01:** 4 lookups." in report.asked(a)


def test_the_report_says_where_you_rank(monkeypatch):
    ranking(monkeypatch)
    text = report.asked(asked.asked(OWN, [Q1], rank=True))
    assert "## Where you rank for the searches they ran" in text
    assert "| google | 3 | 1 | 2 | 0 | 0 | 0 |" in text and "| bing | 3 | 0 | 0 | 0 | 0 | 0 |" in text
    assert "- agent skills directory 2026 (×5: chatgpt, claude): Google #2 (/skills), Bing –" in text
    assert "- claude skills marketplace (×1: claude): Google #11 (/), Bing –" in text
    assert "| list.example | 3 | 1 | 6 |" in text and "| forum.example | 1 | 1 | 0 |" in text
    assert "or known to the model already: reddit.com (2)." in text           # cited by AI Mode and Gemini, never ranked
    assert "Lookups cost $0.021." in text and "Cost of this run: $0.137 (cap $1.00)." in text


def test_no_rank_of_yours_is_said_with_the_searches_read(monkeypatch):
    ranking(monkeypatch)
    text = report.asked(asked.asked("elsewhere.example", [Q1], rank=True))
    assert "elsewhere.example is in neither engine's top 20 for any of the 3 searches read." in text


def test_the_questions_each_assistant_writes_are_merged_once(monkeypatch):
    replies = {"chatgpt": "1. Where can I find agent skills?\n2. “Best Claude skills directory”\nHere you go:",
               "claude": "- where can I find agent skills\n- Which skills help with PDFs?",
               "gemini": "Is there a marketplace for Claude Code skills?"}

    def rest(path, body):
        writer = next(w for w, x in asked.WRITERS.items() if x[0] == path)
        assert body["model_name"] == asked.WRITERS[writer][1] and "web_search" not in body
        return llm(replies[writer], []), 300
    monkeypatch.setattr(asked.aisa, "rest", rest)
    q = asked.write_questions("a directory of agent skills", count=5)
    assert q["by"]["chatgpt"] == ["Where can I find agent skills?", "Best Claude skills directory"]
    # the writers in turn: Claude's first is ChatGPT's again, so Gemini's comes second
    assert q["questions"] == ["Where can I find agent skills?", "Is there a marketplace for Claude Code skills?",
                              "Best Claude skills directory", "Which skills help with PDFs?"]
    assert q["cost"] == 900 and "## All of them once (4)" in report.questions(q)


def test_the_command_line(monkeypatch, tmp_path, capsys):
    world(monkeypatch)
    listed = tmp_path / "q.txt"
    listed.write_text(f"# ours\n{Q1}\n\n")
    assert cli.main(["asked", OWN, "--file", str(listed), "--engines", "chatgpt", "--samples", "1", "--json"]) == 0
    out = capsys.readouterr().out
    assert '"engines": [\n  "chatgpt"\n ]' in out and '"ranks"' not in out
    ranking(monkeypatch)
    assert cli.main(["asked", OWN, Q1, "--engines", "claude", "--rank"]) == 0
    assert "Google #2 (/skills)" in capsys.readouterr().out
