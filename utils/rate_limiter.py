"""Rate limiting utilities for the Payroll WhatsApp Automation System.

Implements a thread-safe Token Bucket rate limiter to ensure outbound
WhatsApp API calls respect the platform's rate limits. Also provides
exponential-backoff helpers for graceful retry logic when the API
returns HTTP 429 (Too Many Requests).
"""

import random
import threading
import time
from typing import Optional


class RateLimiter:
    """Thread-safe rate limiter using the Token Bucket algorithm.

    Args:
        max_per_second: Maximum sustained rate (tokens added per second).
        burst: Maximum number of tokens that can accumulate in the bucket.
    """

    def __init__(self, max_per_second: float = 1.0, burst: int = 1) -> None:
        if max_per_second <= 0:
            raise ValueError("max_per_second must be positive")
        if burst < 1:
            raise ValueError("burst must be at least 1")

        self._max_per_second: float = max_per_second
        self._burst: int = burst

        # Current number of available tokens
        self._tokens: float = float(burst)

        # Timestamp of last token refill (monotonic clock)
        self._last_refill: float = time.monotonic()

        # Lock protecting mutable state
        self._lock: threading.Lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a token is available, then consume it."""
        while True:
            with self._lock:
                self._refill()

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return  # token acquired — proceed

                # Calculate how long until the next token arrives
                deficit: float = 1.0 - self._tokens
                wait_time: float = deficit / self._max_per_second

            # Sleep *outside* the lock so other threads can check too
            time.sleep(wait_time)

    def report_rate_limit(self, retry_after: Optional[float] = None) -> None:
        """Handle an HTTP 429 *Too Many Requests* response."""
        with self._lock:
            # Drain the bucket so subsequent callers also wait
            self._tokens = 0.0

        sleep_duration: float = (
            retry_after if retry_after is not None
            else 1.0 / self._max_per_second
        )
        time.sleep(max(sleep_duration, 0.0))

    @staticmethod
    def get_backoff_delay(
        attempt: int,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
    ) -> float:
        """Calculate an exponential back-off delay with jitter."""
        jitter: float = random.uniform(0.0, 1.0)
        delay: float = base_delay * (2 ** attempt) + jitter
        return min(delay, max_delay)

    def _refill(self) -> None:
        """Add tokens based on elapsed time since the last refill."""
        now: float = time.monotonic()
        elapsed: float = now - self._last_refill
        self._last_refill = now

        self._tokens += elapsed * self._max_per_second
        if self._tokens > self._burst:
            self._tokens = float(self._burst)
