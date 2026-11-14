from pathlib import Path

p = Path(r"D:\LoomShield\backend\rate_limiter.py")
text = p.read_text(encoding="utf-8")

target = """            self.requests = {k: self.requests[k] for k in sorted_keys[: self.max_tracked_ips]}
        return True"""

replacement = """            self.requests = {k: self.requests[k] for k in sorted_keys[: self.max_tracked_ips]}
        return True

    def reset(self):
        with self.lock:
            self.requests.clear()
            self.global_requests.clear()"""

assert target in text
text = text.replace(target, replacement, 1)

p.write_text(text, encoding="utf-8")
print("Added reset() to SimpleIpRateLimiter in backend/rate_limiter.py")
