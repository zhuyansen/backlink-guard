"""A cap on what one run may spend (--max-usd), for the commands whose calls multiply with what they are given.

A paid question is asked only while its estimate still fits under the cap. An answer cached in the last 7 days is
free and always given. A question the cap leaves out is named, so the report can say what is missing instead of
passing a gap off as nothing found. An estimate is a price seen before, an upper bound for the call as it is asked:
AIsa's own quote for these calls ($0.06 for any backlinks call, $0.04 for a results page, 2026-10-20) is so far above
what they cost ($0.025 to $0.03) that it would stop a run long before its cap.

Calls may run side by side (asked.py): while one runs, its estimate is held against the cap, so two calls that each
fit cannot together pass it.
"""
from __future__ import annotations

import threading

from . import cache

MICROS = 1_000_000


class OverBudget(Exception):
    """The next call's estimate does not fit under the cap."""


class Budget:
    def __init__(self, max_usd: float) -> None:
        self.cap = round(max_usd * MICROS)
        self.spent = 0
        self.held = 0                   # the estimates of the calls running now
        self.left_out: list[str] = []
        self._lock = threading.Lock()

    def ask(self, key: str, estimate: int, fetch, fresh: bool = False, what: str = ""):
        """(answer, cost): the answer cached under `key` when there is one, else fetch()'s when `estimate` still fits
        (the answer is then cached). Raises OverBudget, and keeps `what` among the questions left out, when it does not."""
        held = None if fresh else cache.get(key)
        if held is not None:
            return held, 0
        with self._lock:
            if self.spent + self.held + estimate > self.cap:
                self.left_out.append(what or key)
                raise OverBudget(what or key)
            self.held += estimate
        try:
            answer, cost = fetch()
        finally:
            with self._lock:
                self.held -= estimate
        cache.put(key, answer)
        with self._lock:
            self.spent += cost
        return answer, cost
