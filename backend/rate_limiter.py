"""
Simple in-memory rate limiter for LoomShield audit and upload routes.
Provides sliding-window rate limiting per client IP to prevent denial of service.
"""

import time
from collections import defaultdict
from threading import Lock


class SimpleIpRateLimiter:
    """Sliding-window in-memory per-IP rate limiter."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
        self.lock = Lock()

    def is_allowed(self, client_ip: str) -> bool:
        if not client_ip:
            return True
        now = time.time()
        window_start = now - self.window_seconds
        with self.lock:
            # Purge expired timestamps
            self.requests[client_ip] = [t for t in self.requests[client_ip] if t > window_start]
            if len(self.requests[client_ip]) >= self.max_requests:
                return False
            self.requests[client_ip].append(now)
            return True

    def reset(self) -> None:
        with self.lock:
            self.requests.clear()
