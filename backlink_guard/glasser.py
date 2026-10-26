"""Glasser's Run API (glasser.ai): the same backlink, search and keyword endpoints AIsa resells, one Run a task.
Key: GLASSER_API_KEY. When it is set, backend.py sends those calls here instead of to AIsa.

Prices in Glasser's catalog (2026-10-26), the same as AIsa charges for the same calls but for two
searches: the backlink endpoints $0.024 a call plus $0.000036 a row, keyword overview about $0.012,
a site's technologies $0.012. Google's regular result page is $0.002 a page of ten, so find's 30
results cost $0.006 here and $0.005 through AIsa; the advanced page with its AI Overview (cited) up
to $0.006 here, $0.004 through AIsa. A Run that finds nothing is billed, a task the provider refuses
is not; none is retried here, and a Run still queued or running is polled by its id, never created
twice. Searches with operators (site:, inurl:) are not sold: vet.index_count asks AIsa for those.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from decimal import Decimal, InvalidOperation

from . import UA
from .aisa import AisaError

BASE = os.environ.get("GLASSER_BASE_URL", "https://api.glasser.ai") + "/v1/runs"
TIMEOUT = 240
POLL_SECONDS = 2
MAX_POLLS = 60
PENDING = ("QUEUED", "RUNNING")
OK, NO_DATA = 20000, 40102      # the provider's "Ok." and "No Search Results.": a site it knows nothing about
# The AIsa tool each caller names -> the endpoint on Glasser and the contract version this module was
# checked against (2026-10-26; a retired version answers 409).
ENDPOINTS = {
    "post_dataforseo_serp_google_organic_live_regular": ("/v3/serp/google/organic/live/regular", 6),
    "post_dataforseo_serp_google_organic_live": ("/v3/serp/google/organic/live/advanced", 7),
    "post_dataforseo_labs_google_keyword_overview_live": ("/v3/dataforseo_labs/google/keyword_overview/live", 6),
    "post_dataforseo_labs_google_historical_bulk_traffic_live":
        ("/v3/dataforseo_labs/google/historical_bulk_traffic_estimation/live", 2),
    "post_dataforseo_backlinks_backlinks_live": ("/v3/backlinks/backlinks/live", 9),
    "post_dataforseo_backlinks_referring_domains_live": ("/v3/backlinks/referring_domains/live", 7),
    "post_dataforseo_backlinks_domain_intersection_live": ("/v3/backlinks/domain_intersection/live", 6),
    "post_dataforseo_backlinks_timeseries_new_lost_live": ("/v3/backlinks/timeseries_new_lost_summary/live", 1),
    "post_dataforseo_backlinks_anchors_live": ("/v3/backlinks/anchors/live", 7),
    "post_dataforseo_backlinks_summary_live": ("/v3/backlinks/summary/live", 2),
    "post_dataforseo_backlinks_bulk_spam_score_live": ("/v3/backlinks/bulk_spam_score/live", 2),
    "post_dataforseo_domains_tech_for_domain_live": ("/v3/domain_analytics/technologies/domain_technologies/live", 2),
    "post_dataforseo_ai_llm_mentions_aggregated_metrics_live": ("/v3/ai_optimization/llm_mentions/target_metrics/live", 1),
}
# AIsa's passthrough paths (aisa.rest) -> the same endpoints by their tool names.
REST = {"backlinks/backlinks/live": "post_dataforseo_backlinks_backlinks_live",
        "backlinks/referring_domains/live": "post_dataforseo_backlinks_referring_domains_live",
        "backlinks/domain_intersection/live": "post_dataforseo_backlinks_domain_intersection_live"}


class GlasserError(AisaError):
    """A Glasser Run that failed or could not be read. An AisaError, so the callers that already
    report AIsa's failures report these the same way."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise GlasserError("Glasser redirect refused: the key stays on api.glasser.ai")


_OPENER = urllib.request.build_opener(_NoRedirect())


def key() -> str:
    return os.environ.get("GLASSER_API_KEY", "").strip()


def _request(url: str, body: dict | None = None, request_id: str = "") -> dict:
    headers = {"Authorization": f"Bearer {key()}", "Accept": "application/json", "User-Agent": UA}
    if body is not None:
        headers.update({"Content-Type": "application/json", "Idempotency-Key": request_id})
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers, method="POST" if body is not None else "GET")
    try:
        with _OPENER.open(req, timeout=TIMEOUT) as res:
            answer = json.load(res)
    except urllib.error.HTTPError as exc:
        raise GlasserError(f"Glasser HTTP {exc.code}: {_reason(exc)}") from None
    except (OSError, ValueError) as exc:
        raise GlasserError(f"Glasser {type(exc).__name__}; the Run may still have been billed") from None
    if not isinstance(answer, dict) or answer.get("error"):
        raise GlasserError(f"Glasser error: {str((answer or {}).get('error'))[:160]}")
    return answer


def _reason(exc: urllib.error.HTTPError) -> str:
    """The error message Glasser gives, with its detail ("search operators such as site: ... are not sold"),
    never the request: it carries the key."""
    try:
        err = json.loads(exc.read().decode("utf-8", "replace")).get("error") or {}
    except (ValueError, AttributeError):
        return "no detail"
    if not isinstance(err, dict):
        return str(err)[:160]
    detail = (err.get("details") or {}).get("issues") if isinstance(err.get("details"), dict) else None
    return str(err.get("message") or err.get("code") or err)[:160] + (f" ({str(detail)[:160]})" if detail else "")


def _settle(run: dict) -> dict:
    """Poll a queued or running Run by its id until it ends or MAX_POLLS runs out."""
    run_id = str(run.get("id") or "")
    for _ in range(MAX_POLLS):
        if run.get("status") not in PENDING:
            return run
        time.sleep(POLL_SECONDS)
        run = _request(f"{BASE}/{urllib.parse.quote(run_id, safe='')}")
    raise GlasserError(f"Run {run_id} still {run.get('status')}: look it up in Glasser before running it again")


def _charge(run: dict) -> int:
    try:
        return int((Decimal(str(run["charge_usd"])) * 1_000_000).to_integral_value())
    except (KeyError, InvalidOperation):
        raise GlasserError(f"Run {run.get('id')}: no readable charge_usd") from None


def run(endpoint: str, version: int, task: dict) -> tuple[dict, int]:
    """One task as one Run: (the provider's own response, cost in micro-USD)."""
    request_id = str(uuid.uuid4())
    done = _settle(_request(BASE, {"provider": "dataforseo", "endpoint": endpoint, "endpoint_version": version,
                                   "input": task}, request_id))
    if done.get("status") != "COMPLETED":
        failure = f": {str(done['failure'])[:120]}" if done.get("failure") else ""
        raise GlasserError(f"Run {done.get('id')} ended {done.get('status')}{failure}")
    provider = done.get("provider_response") or {}
    status = provider.get("http_status")
    if not isinstance(status, int) or not 200 <= status < 300:
        raise GlasserError(f"Run {done.get('id')}: the provider answered HTTP {status}")
    refused = provider.get("error")         # a task the provider refused comes back here, with no output
    return done.get("output") or (refused if isinstance(refused, dict) else {}), _charge(done)


def _task(output: dict) -> dict:
    """The response's one task; NO_DATA is an answer (nothing known), any other status a failure."""
    task = (output.get("tasks") or [{}])[0] or {}
    if output.get("status_code") != OK or task.get("status_code") not in (OK, NO_DATA):
        raise GlasserError(str(task.get("status_message") or output.get("status_message") or "call failed")[:160])
    return task


def call(tool: str, body: dict) -> tuple[dict, int]:
    """aisa.call() through Glasser: (the task's first result, cost in micro-USD); no result raises."""
    if tool not in ENDPOINTS:
        raise GlasserError(f"{tool} is not mapped to Glasser")
    output, cost = run(*ENDPOINTS[tool], body)
    task = _task(output)
    if not task.get("result"):
        raise GlasserError("no result")         # the callers read it as nothing known, as from aisa.call
    return task["result"][0] or {}, cost


def rest(path: str, body: dict) -> tuple[dict, int]:
    """aisa.rest() through Glasser: (the task's first result or {}, cost in micro-USD)."""
    if path not in REST:
        raise GlasserError(f"{path} is not mapped to Glasser")
    output, cost = run(*ENDPOINTS[REST[path]], body)
    return (_task(output).get("result") or [{}])[0] or {}, cost
