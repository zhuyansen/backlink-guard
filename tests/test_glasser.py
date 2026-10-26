"""Glasser: the same data as AIsa's, asked first when its key is set (0.9). No network: Glasser's answers are stubbed."""
import io
import json
import urllib.error
from datetime import date

import pytest

from backlink_guard import backend, checkout, cited, competitors, find, glasser, history, links, owners, profile, report, signals, vet

TODAY = date(2026, 10, 13)


def run_of(status, output=None, http=200, charge="0.024036"):
    return {"id": "run_1", "status": status, "charge_usd": charge, "provider_response": {"http_status": http}, "output": output}


def task_output(result, code=20000, message="Ok."):
    return {"status_code": 20000, "tasks": [{"status_code": code, "status_message": message, "result": result}]}


def test_glasser_answers_when_its_key_is_set_else_aisa(monkeypatch):
    asked = []
    monkeypatch.setattr(backend.glasser, "call", lambda tool, body: (asked.append("glasser"), ({"x": 1}, 10))[1])
    monkeypatch.setattr(backend.aisa, "call", lambda tool, body: (asked.append("aisa"), ({"x": 2}, 20))[1])
    assert backend.key() == ""
    monkeypatch.setattr(backend.aisa, "key", lambda: "a")
    assert backend.call(vet.SPAM_TOOL, {}) == ({"x": 2}, 20) and backend.name() == "AIsa"
    monkeypatch.setenv("GLASSER_API_KEY", "g")
    assert backend.call(vet.SPAM_TOOL, {}) == ({"x": 1}, 10) and asked == ["aisa", "glasser"]
    assert backend.key() == "g" and backend.name() == "Glasser"


def test_every_call_the_backend_routes_is_mapped_to_glasser():
    tools = {vet.SPAM_TOOL, vet.SUMMARY_TOOL, find.SERP_TOOL, find.VOLUME_TOOL, history.TOOL, profile.NEW_LOST_TOOL,
             profile.ANCHORS_TOOL, links.TOOL, checkout.TOOL, owners.REFERRING_TOOL, signals.TECH_TOOL, signals.MENTIONS_TOOL,
             cited.TOOL}
    assert tools <= set(glasser.ENDPOINTS)
    assert {competitors.REFERRING, competitors.INTERSECTION, competitors.BACKLINKS, "backlinks/backlinks/live"} <= set(glasser.REST)
    assert signals.AHREFS_TOOL not in glasser.ENDPOINTS and signals.SEMRUSH_TOOL not in glasser.ENDPOINTS   # AIsa's alone


def test_a_glasser_run_is_polled_by_its_id_never_created_twice(monkeypatch):
    sent = []
    answers = iter([run_of("QUEUED"), run_of("RUNNING"), run_of("COMPLETED", task_output([{"items": [1]}]))])

    def request(url, body=None, request_id=""):
        sent.append((url, body is not None))
        return next(answers)
    monkeypatch.setattr(glasser, "_request", request)
    monkeypatch.setattr(glasser, "POLL_SECONDS", 0)
    assert glasser.call(vet.SPAM_TOOL, {"targets": ["a.dev"]}) == ({"items": [1]}, 24036)
    assert [posted for _, posted in sent] == [True, False, False] and sent[1][0].endswith("/v1/runs/run_1")


def test_a_glasser_run_carries_the_key_the_endpoint_and_a_fresh_idempotency_key(monkeypatch):
    monkeypatch.setenv("GLASSER_API_KEY", "gl_test")
    seen = []

    def answer(req, timeout):
        seen.append(req)
        return io.BytesIO(json.dumps(run_of("COMPLETED", task_output([{"items": []}]))).encode())
    monkeypatch.setattr(glasser._OPENER, "open", answer)
    glasser.call(vet.SPAM_TOOL, {"targets": ["a.dev"]})
    glasser.call(vet.SPAM_TOOL, {"targets": ["b.dev"]})
    assert json.loads(seen[0].data) == {"provider": "dataforseo", "endpoint": "/v3/backlinks/bulk_spam_score/live",
                                        "endpoint_version": 2, "input": {"targets": ["a.dev"]}}
    assert seen[0].get_header("Authorization") == "Bearer gl_test"
    ids = [r.get_header("Idempotency-key") for r in seen]
    assert all(ids) and ids[0] != ids[1]


def refusing(code, body):
    def refuse(req, timeout):
        raise urllib.error.HTTPError(req.full_url, code, "refused", {}, io.BytesIO(json.dumps(body).encode()))
    return refuse


def test_a_glasser_http_error_gives_its_message_and_detail_never_the_request(monkeypatch):
    monkeypatch.setenv("GLASSER_API_KEY", "gl_secret")
    monkeypatch.setattr(glasser._OPENER, "open", refusing(402, {"error": {"code": "insufficient_balance",
                                                                          "message": "Top up to run this."}}))
    with pytest.raises(glasser.GlasserError) as exc:
        glasser.call(vet.SPAM_TOOL, {"targets": ["a.dev"]})
    assert str(exc.value) == "Glasser HTTP 402: Top up to run this." and "gl_secret" not in str(exc.value)
    monkeypatch.setattr(glasser._OPENER, "open", refusing(400, {"error": {     # as Glasser answered a site: search, 2026-10-26
        "code": "validation_failed", "message": "Input does not match the endpoint's input schema",
        "details": {"issues": "SchemaError(search operators such as site: or inurl: are not sold on this Endpoint)"}}}))
    with pytest.raises(glasser.GlasserError, match="search operators such as site: or inurl: are not sold"):
        glasser.call(find.SERP_TOOL, {"keyword": "site:a.dev"})


@pytest.mark.parametrize("run, says", [
    (run_of("FAILED"), "ended FAILED"),
    (run_of("COMPLETED", task_output([]), http=500), "the provider answered HTTP 500"),
    (run_of("COMPLETED", task_output(None, 40501, "Invalid Field.")), "Invalid Field"),
    (run_of("COMPLETED", task_output(None, 40102, "No Search Results.")), "no result"),     # read as zero, as from AIsa
    (run_of("COMPLETED", task_output([])), "no result"),
    (run_of("COMPLETED", task_output([{}]), charge=None), "no readable charge_usd"),
])
def test_glasser_failures_raise_as_the_aisa_errors_callers_catch(monkeypatch, run, says):
    monkeypatch.setattr(glasser, "_request", lambda url, body=None, request_id="": run)
    with pytest.raises(vet.aisa.AisaError, match=says):
        glasser.call(vet.SPAM_TOOL, {"targets": ["a.dev"]})


def test_a_task_the_provider_refuses_keeps_its_message(monkeypatch):
    refused = {"status_code": 20000, "tasks": [{"status_code": 40501, "status_message": "Invalid Field: 'target'.", "result": None}]}
    monkeypatch.setattr(glasser, "_request", lambda url, body=None, request_id="": {   # the shape seen on 2026-10-26, not billed
        "id": "run_2", "status": "COMPLETED", "output": None, "charge_usd": "0.00",
        "provider_response": {"http_status": 200, "error": refused}})
    with pytest.raises(glasser.GlasserError, match="Invalid Field: 'target'"):
        glasser.call(signals.TECH_TOOL, {"target": "no-such-site.dev"})


def test_glasser_passthrough_reads_no_data_as_nothing_found(monkeypatch):
    monkeypatch.setattr(glasser, "_request", lambda url, body=None, request_id="": run_of(
        "COMPLETED", task_output(None, 40102, "No Search Results.")))
    assert glasser.rest("backlinks/backlinks/live", {"target": "stripe.com"}) == ({}, 24036)
    with pytest.raises(glasser.GlasserError, match="not mapped"):
        glasser.rest("backlinks/anchors/live", {})


def test_the_site_search_stand_in_asks_aisa_never_glasser(monkeypatch):
    def down(path, **params):
        raise vet.goanyapi.GoAnyError("HTTP 502")
    monkeypatch.setattr(vet.goanyapi, "call", down)
    monkeypatch.setenv("GLASSER_API_KEY", "g")
    monkeypatch.setattr(glasser, "call", lambda tool, body: pytest.fail("Glasser sells no site: searches"))
    with pytest.raises(vet.goanyapi.GoAnyError):                # Glasser alone: the failure stands
        vet.index_count("dir.example", fresh=True)
    monkeypatch.setattr(vet.aisa, "key", lambda: "a")
    monkeypatch.setattr(vet.aisa, "call", lambda tool, body: ({"se_results_count": 40, "items": []}, 10000))
    assert vet.index_count("dir.example", fresh=True) == (40, 10000)


def test_deep_with_glasser_only_leaves_out_ahrefs_and_semrush_and_says_so(monkeypatch):
    monkeypatch.setenv("GLASSER_API_KEY", "g")

    def call(name, body):
        if name == signals.TECH_TOOL:
            return {"technologies": {"cms": {"cms": ["WordPress"]}}}, 12000
        return {"total": {"platform": [{"key": "chat_gpt", "mentions": 3}]}}, 101000
    monkeypatch.setattr(glasser, "call", call)
    monkeypatch.setattr(signals.aisa, "tool", lambda name, args: pytest.fail("Ahrefs and Semrush are AIsa's"))
    got, cost, errors = signals.deep("x.dev", TODAY, lambda q, fn: fn())
    assert got == {"tech": ["WordPress"], "ai_mentions": 3} and cost == 113000 and not errors
    head = report.audience_lines([{"domain": "x.dev", "metrics": {"registered": "2020-01-01", **got}}])[3]
    assert "ChatGPT mentions" in head                   # the columns show without Ahrefs' or Semrush's numbers
    assert report.missing_sources({"goanyapi": True, "glasser": True, "aisa": False, "deep": True}) == [
        "- No `AISA_API_KEY`: `--deep` left out Ahrefs' rating and Semrush's numbers (Glasser does not sell them)."]
    assert report.missing_sources({"goanyapi": True, "glasser": True, "aisa": False, "deep": False}) == []
    assert report.missing_sources({"goanyapi": True, "glasser": False, "aisa": False}) == [
        "- No `GLASSER_API_KEY` or `AISA_API_KEY`: spam scores and Google search history were not checked."]


def test_chatgpt_mentions_come_from_either_answer_shape():
    answer = {"items": [], "items_count": 0, "aggregated_metrics": {      # trimmed from Glasser's answer, 2026-10-26
        "total": {"mentions": 29, "ai_search_volume": 5679},
        "platform": [{"key": "chat_gpt", "mentions": 29, "ai_search_volume": 5679}],
        "sources_domain": [{"key": "www.reddit.com", "mentions": 6}]}}
    assert signals.mentions(answer) == 29 and signals.mentions({"total": {"platform": [{"mentions": 910}]}}) == 910
    assert signals.mentions(None) == 0


def test_the_evidence_names_who_answered(monkeypatch):
    monkeypatch.setenv("GLASSER_API_KEY", "g")
    item = {"url_from": "https://a.example/x", "url_to": "https://mine.example/", "anchor": "Mine", "domain_from_rank": 120,
            "dofollow": True}
    monkeypatch.setattr(glasser, "call", lambda tool, body: ({"total_count": 3, "items": [item]}, 24036))
    got = links.fetch("mine.example", True, limit=10)
    assert (got["source"], got["strength"], got["total"]) == ("Glasser", "Glasser rank", 3)
    row = {"domain": "x.dev", "input": "x.dev", "url": "https://x.dev", "flags": [], "errors": [], "cost": 0,
           "metrics": {"spam_score": 60, "spam_by": "Glasser"}}
    assert "60 of 100 (Glasser)" in [f["evidence"] for f in vet.finalize(row)["flags"]]
    saved = dict(row, flags=[], metrics={"spam_score": 60})              # a row saved before 0.9: AIsa said it
    assert "60 of 100 (AIsa)" in [f["evidence"] for f in vet.finalize(saved)["flags"]]


def test_cited_holds_glassers_dearer_page_against_the_cap(monkeypatch):
    calls = []

    def call(tool, body):
        calls.append(body["keyword"])
        return {"items": []}, 4000
    monkeypatch.setattr(glasser, "call", call)
    monkeypatch.setattr(cited.aisa, "call", call)
    words = ["agent skills", "skill directory", "claude skills"]
    monkeypatch.setenv("GLASSER_API_KEY", "g")
    through_glasser = cited.cited("mine.example", words, max_usd=0.013)        # up to $0.006 a keyword
    assert calls == words[:2] and through_glasser["left_out"] == ["“claude skills”"]
    monkeypatch.delenv("GLASSER_API_KEY")
    calls.clear()
    through_aisa = cited.cited("mine.example", words, max_usd=0.013, fresh=True)    # up to $0.004
    assert calls == words and through_aisa["left_out"] == []
