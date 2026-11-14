import urllib.request
import json
import sys

base = "http://127.0.0.1:8000"
endpoints = [
    ("/favicon.ico", 200, "image/x-icon"),
    ("/favicon.svg", 200, "image/svg+xml"),
    ("/apple-touch-icon.png", 200, "image/png"),
    ("/static/favicon.svg", 200, "image/svg+xml"),
    ("/static/favicon-16x16.png", 200, "image/png"),
    ("/static/favicon-32x32.png", 200, "image/png"),
    ("/static/apple-touch-icon.png", 200, "image/png"),
    ("/static/favicon.ico", 200, None),
]

for path, expected_code, expected_type in endpoints:
    url = base + path
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as res:
            code = res.getcode()
            content_type = res.headers.get("Content-Type")
            data = res.read()
            assert code == expected_code, f"Expected {expected_code}, got {code}"
            if expected_type:
                assert expected_type in content_type, f"Expected {expected_type} in {content_type}"
            print(f"PASS: {path} -> {code} ({content_type}, {len(data)} bytes)")
    except Exception as e:
        print(f"FAIL: {path} -> {e}")
        sys.exit(1)

# Check index.html head tags
with urllib.request.urlopen(base + "/", timeout=5) as res:
    html = res.read().decode("utf-8")
    assert 'rel="icon"' in html
    assert "favicon.svg" in html
    assert "favicon-32x32.png" in html
    assert "favicon-16x16.png" in html
    assert "favicon.ico" in html
    assert "apple-touch-icon.png" in html
    print("PASS: index.html contains all 5 favicon declarations")

# Check Audit History rendered HTML logic in app.js
with open(r"D:\LoomShield\frontend\app.js", "r", encoding="utf-8") as f:
    js = f.read()
    assert "Version timeline" not in js, "Version timeline should be completely removed from app.js"
    assert "Approval &amp; content-integrity events" in js
    assert "No approval events recorded yet." in js
    print("PASS: Version timeline is removed from app.js; Approval events & empty state verified")

print("\nALL VERIFICATIONS PASSED!")
