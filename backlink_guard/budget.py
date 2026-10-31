"""A cap on what one run may spend (--max-usd), for the commands whose calls multiply with what they are given.

A paid question is asked only while its estimate still fits under the cap. An answer cached in the last 7 days is
free and always given. A question the cap leaves out is named, so the report can say what is missing instead of
passing a gap off as nothing found.

The cap is kept on estimates, so it holds as far as they do. An estimate is a price seen before, at or above what the
call cost when it was set, not a price the provider guarantees: a model's answer that runs long, or a price raised
since, can bill a call above its estimate and the run above the cap by the difference. What a call cost is counted as
soon as it returns, so every call after it is weighed against that. AIsa's own quote for these calls ($0.06 for any
backlinks call, $0.04 for a results page, 2026-10-20) is so far above what they cost ($0.025 to $0.03) that it would
stop a run long before its cap.

Calls may run side by side (asked.py): while one runs, its estimate is held against the cap, so two calls that each
fit cannot together pass it. When it returns, its estimate is replaced by what it cost in one step, before its answer
is written to the cache, so no call is let in meanwhile against room that is already spent.
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
        cost = 0                        # what a failed call costs
        try:
            answer, cost = fetch()
        finally:
            # the estimate becomes the cost in one step, before the cache is written, so no call is let in meanwhile
            # against room this one has already spent
            with self._lock:
                self.held -= estimate
                self.spent += cost
        cache.put(key, answer)
        return answer, cost
