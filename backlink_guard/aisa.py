"""AIsa's tool router: DataForSEO's backlink data (spam score, new and lost referring
domains, anchors). Key: AISA_API_KEY, or the one the AIsa CLI stores at login.

Every call is billed and none is retried here. Prices seen on 2026-10-13: spam score for
14 domains in one call $0.025, a new/lost timeline $0.025, anchors about $0.04.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from . import UA

ROUTER = os.environ.get("AISA_ROUTER_BASE_URL", "https://tools.aisa.one") + "/v1/tool-router/aisa-batch-use"
TIMEOUT = 240


class AisaError(RuntimeError):
    pass


def key() -> str:
    """"" when there is no key: callers skip this source, they do not fail."""
    if os.environ.get("AISA_API_KEY"):
        return os.environ["AISA_API_KEY"].strip()
    stored = Path.home() / ".aisa" / "key"
    return stored.read_text().strip() if stored.exists() else ""


def call(tool: str, body: dict) -> tuple[dict, int]:
    """One DataForSEO task. Returns (the task's first result, cost in micro-USD)."""
    payload = {"calls": [{"call_id": "c", "tool": tool, "arguments": {"body": [body]}}]}
    req = urllib.request.Request(ROUTER, data=json.dumps(payload).encode(), method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key()}", "User-Agent": UA,
        "x-aisa-source": "backlink-guard"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            reply = json.load(res)
    except urllib.error.HTTPError as exc:
        raise AisaError(f"HTTP {exc.code}: {' '.join(exc.read().decode('utf-8', 'replace').split())[:160]}") from exc
    except (OSError, ValueError) as exc:
        raise AisaError(f"{type(exc).__name__}: {exc}") from exc
    row = (reply.get("results") or [{}])[0]
    if "error" in reply or not row.get("successful"):
        raise AisaError(str(reply.get("error") or row.get("error") or "call failed")[:160])
    task = ((row.get("data") or {}).get("tasks") or [{}])[0]
    if not task.get("result"):
        raise AisaError(str(task.get("status_message") or "no result")[:160])
    return task["result"][0] or {}, int(row.get("customer_cost_micros_usd") or 0)
