"""
Simple in-memory rate limiter for LoomShield audit and upload routes.
Provides sliding-window rate limiting per client IP, global request ceilings,
and safe client IP extraction with reverse proxy hop resolution and IP validation.
"""

import ipaddress
import os
import time
from collections import defaultdict
from threading import Lock


class SimpleIpRateLimiter:
    """Sliding-window in-memory per-IP and global rate limiter with idle key eviction."""

    def __init__(
        self,
        max_requests: int = 30,
        window_seconds: int = 60,
        global_max_requests: int = 300,
        max_tracked_ips: int = 2000,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.global_max_requests = global_max_requests
        self.max_tracked_ips = max_tracked_ips
        self.requests = defaultdict(list)
        self.global_requests = []
        self.lock = Lock()

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        with self.lock:
            # 1. Global ceiling check
            self.global_requests = [t for t in self.global_requests if t > window_start]
            if len(self.global_requests) >= self.global_max_requests:
                return False

            ip_key = client_ip.strip() if client_ip else "127.0.0.1"

            # 2. Per-IP window check
            ip_history = [t for t in self.requests.get(ip_key, []) if t > window_start]
            if len(ip_history) >= self.max_requests:
                self.requests[ip_key] = ip_history
                return False

            ip_history.append(now)
            self.requests[ip_key] = ip_history
            self.global_requests.append(now)

            # 3. Purge idle keys and cap tracked keys
            if len(self.requests) > 200:
                idle = [k for k, ts in self.requests.items() if not ts or ts[-1] <= window_start]
                for k in idle:
                    del self.requests[k]
                if len(self.requests) > self.max_tracked_ips:
                    sorted_keys = sorted(
                        self.requests.keys(),
                        key=lambda k: self.requests[k][-1] if self.requests[k] else 0,
                    )
                    to_remove = len(self.requests) - self.max_tracked_ips
                    for k in sorted_keys[:to_remove]:
                        del self.requests[k]

            return True

    def reset(self) -> None:
        with self.lock:
            self.requests.clear()
            self.global_requests.clear()


def is_valid_ip(candidate: str) -> bool:
    """Validate that candidate string is a well-formed IPv4 or IPv6 address."""
    if not candidate or not isinstance(candidate, str):
        return False
    try:
        ipaddress.ip_address(candidate.strip())
        return True
    except (ValueError, AttributeError):
        return False


def get_client_ip(request) -> str:
    """Extract client IP safely from forwarded headers behind Render's reverse proxy.

    Prevents spoofing of leftmost X-Forwarded-For or x-vercel-forwarded-for headers:
    1. x-vercel-forwarded-for: honoured ONLY when LOOMSHIELD_TRUST_VERCEL_HEADER=1 is explicitly set.
    2. x-forwarded-for: Render's ingress proxy appends the connecting client IP as the rightmost hop.
       Resolves hops[-trusted_hops] (default LOOMSHIELD_TRUSTED_PROXY_HOPS=1 -> hops[-1]), walking
       right-to-left so client-prepended fake IPs are ignored while keeping each user in their own bucket.
    3. x-real-ip: verified fallback.
    4. request.client.host: direct socket connection fallback.
    """
    if not request:
        return "127.0.0.1"

    headers = getattr(request, "headers", {})

    # 1. Check x-vercel-forwarded-for ONLY when explicitly trusted via LOOMSHIELD_TRUST_VERCEL_HEADER=1
    if os.environ.get("LOOMSHIELD_TRUST_VERCEL_HEADER", "").strip() == "1":
        x_vff = headers.get("x-vercel-forwarded-for")
        if x_vff:
            candidate = x_vff.split(",")[-1].strip()
            if is_valid_ip(candidate):
                return candidate

    # 2. Check x-forwarded-for from the right (Render appends connecting client IP at hops[-1])
    xff = headers.get("x-forwarded-for")
    if xff:
        try:
            trusted_hops = max(1, int(os.environ.get("LOOMSHIELD_TRUSTED_PROXY_HOPS", "1") or "1"))
        except ValueError:
            trusted_hops = 1
        hops = [h.strip() for h in xff.split(",") if h.strip()]
        if hops:
            start_idx = max(0, len(hops) - trusted_hops)
            for idx in range(start_idx, -1, -1):
                if is_valid_ip(hops[idx]):
                    return hops[idx]
            for idx in range(len(hops) - 1, start_idx, -1):
                if is_valid_ip(hops[idx]):
                    return hops[idx]

    # 3. Check x-real-ip
    x_real_ip = headers.get("x-real-ip")
    if x_real_ip and is_valid_ip(x_real_ip.strip()):
        return x_real_ip.strip()

    # 4. Direct socket client
    client = getattr(request, "client", None)
    if client:
        host = getattr(client, "host", None)
        if host and is_valid_ip(host):
            return host

    return "127.0.0.1"
