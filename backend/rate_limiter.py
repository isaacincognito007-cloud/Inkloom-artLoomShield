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


def get_client_ip(request) -> str:
    """Extract client IP safely from forwarded headers or direct connection."""
    if not request:
        return "127.0.0.1"
    headers = getattr(request, "headers", {})
    xff = headers.get("x-forwarded-for")
    if xff:
        # Leftmost entry is the initial client
        client_ip = xff.split(",")[0].strip()
        if client_ip:
            return client_ip
    x_real_ip = headers.get("x-real-ip")
    if x_real_ip and x_real_ip.strip():
        return x_real_ip.strip()
    client = getattr(request, "client", None)
    if client and getattr(client, "host", None):
        return client.host
    return "127.0.0.1"
