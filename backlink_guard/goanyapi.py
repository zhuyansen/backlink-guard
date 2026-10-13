"""GoAnyAPI (goanyapi.com): a domain's rating, a year of monthly visits, whether Google
still lists it, and a summary of its backlinks. Key: GOANYAPI_API_KEY.

One credit is $0.001. Seen on 2026-10-13: rating 2 credits; traffic, site search and
backlinks 4 each; 5 to 10 seconds a call. The service is young (first released August
2026), so a failed call is tried once more and then reported, never fatal.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from . import UA

BASE = os.environ.get("GOANYAPI_BASE_URL", "https://api.goanyapi.com") + "/api/v1/"
TIMEOUT = 60
TRIES = 2
MICROS_PER_CREDIT = 1000


class GoAnyError(RuntimeError):
    pass


def key() -> str:
    return os.environ.get("GOANYAPI_API_KEY", "").strip()


def call(path: str, **params) -> tuple[dict, int]:
    """One GET. Returns (data, cost in micro-USD)."""
    req = urllib.request.Request(BASE + path + "?" + urllib.parse.urlencode(params), headers={
        "authorization": f"Bearer {key()}", "accept": "application/json", "user-agent": UA})
    error = ""
    for _ in range(TRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
                reply = json.load(res)
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}"
            if exc.code < 500:
                break
            continue
        except (OSError, ValueError) as exc:
            error = f"{type(exc).__name__}: {exc}"
            continue
        if reply.get("code") != "ok":
            raise GoAnyError(str(reply.get("message") or reply)[:160])
        data = reply.get("data") or {}
        return data, int(data.get("costCredits") or 0) * MICROS_PER_CREDIT
    raise GoAnyError(error[:160])
