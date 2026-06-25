"""
rate_limit.py
=============
A tiny in-memory sliding-window rate limiter. Used to:

    - throttle login/registration attempts (brute-force protection)
    - throttle session/API call volume on the crypto endpoints

No external dependency (e.g. Flask-Limiter) is required, so the project
keeps its short install list. State lives in a process-local dict, which
is the right tradeoff for a single-instance local app (this server is
documented as 127.0.0.1-only, run by one user at a time).

Usage:
    limiter = RateLimiter()

    allowed, retry_after = limiter.hit("login:" + ip, max_hits=5, window_seconds=60)
    if not allowed:
        return jsonify({"error": f"Too many attempts. Try again in {retry_after}s."}), 429
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, max_hits: int, window_seconds: int) -> tuple[bool, int]:
        """
        Records one "hit" for `key` and reports whether it's allowed under
        a sliding window of `window_seconds` permitting `max_hits` events.

        Returns (allowed: bool, retry_after_seconds: int). retry_after is
        0 when allowed is True.
        """
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]

            # drop timestamps that have fallen out of the window
            while q and (now - q[0]) > window_seconds:
                q.popleft()

            if len(q) >= max_hits:
                retry_after = int(window_seconds - (now - q[0])) + 1
                return False, max(retry_after, 1)

            q.append(now)
            return True, 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)
