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


def _socket_client_ip(request) -> str:
    """Extract direct socket client IP if valid, otherwise default to 127.0.0.1."""
    client = getattr(request, "client", None)
    if client:
        host = getattr(client, "host", None)
        if host and is_valid_ip(host):
            return host.strip()
    return "127.0.0.1"


def get_client_ip(request) -> str:
    """Extract client IP safely with explicit proxy hop and header controls (Part A1).

    Order of resolution:
    1. LOOMSHIELD_CLIENT_IP_HEADER (e.g. cf-connecting-ip): used only when explicitly set and valid.
    2. x-vercel-forwarded-for: trusted only when LOOMSHIELD_TRUST_VERCEL_HEADER=1 and valid.
    3. x-real-ip: trusted only when LOOMSHIELD_TRUST_X_REAL_IP=1 and valid.
    4. x-forwarded-for: LOOMSHIELD_TRUSTED_PROXY_HOPS = N (number of trusted proxy entries on the RIGHT,
       default N=1). Selects hops[-(N+1)] if len(hops) > N and valid, else falls back to socket address.
    5. Direct socket client address (or 127.0.0.1 fallback).
    """
    if not request:
        return "127.0.0.1"

    headers = getattr(request, "headers", {}) or {}
    socket_ip = _socket_client_ip(request)

    # 1. Optional explicit client IP header (e.g. cf-connecting-ip)
    custom_hdr = os.environ.get("LOOMSHIELD_CLIENT_IP_HEADER", "").strip().lower()
    if custom_hdr:
        raw_custom = headers.get(custom_hdr)
        if raw_custom:
            candidate = raw_custom.split(",")[0].strip()
            if is_valid_ip(candidate):
                return candidate

    # 2. x-vercel-forwarded-for behind explicit flag
    if os.environ.get("LOOMSHIELD_TRUST_VERCEL_HEADER", "").strip() == "1":
        x_vff = headers.get("x-vercel-forwarded-for")
        if x_vff:
            candidate = x_vff.split(",")[-1].strip()
            if is_valid_ip(candidate):
                return candidate

    # 3. x-real-ip behind explicit flag
    if os.environ.get("LOOMSHIELD_TRUST_X_REAL_IP", "").strip() == "1":
        x_real_ip = headers.get("x-real-ip")
        if x_real_ip and is_valid_ip(x_real_ip.strip()):
            return x_real_ip.strip()

    # 4. x-forwarded-for with N trusted proxy entries on the RIGHT (default N=1)
    xff = headers.get("x-forwarded-for")
    if xff:
        raw_n = os.environ.get("LOOMSHIELD_TRUSTED_PROXY_HOPS", "1").strip()
        try:
            n_hops = max(0, int(raw_n))
        except ValueError:
            n_hops = 1
        hops = [h.strip() for h in xff.split(",") if h.strip()]
        if len(hops) > n_hops:
            candidate = hops[-(n_hops + 1)]
            if is_valid_ip(candidate):
                return candidate
        return socket_ip

    return socket_ip
