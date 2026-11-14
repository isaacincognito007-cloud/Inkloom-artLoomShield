import sys
import os
import json
import urllib.request
import urllib.error
import subprocess
import time

def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.getcode(), response.read()

def post(url, data=b"", headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.getcode(), response.read()

def main():
    print("Starting LoomShield server...")
    proc = subprocess.Popen(
        [sys.executable, "run_loomshield.py", "--host", "127.0.0.1", "--port", "8765"],
        cwd="D:\\LoomShield",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        url = "http://127.0.0.1:8765"
        for _ in range(30):
            try:
                code, body = get(f"{url}/api/health")
                if code == 200:
                    data = json.loads(body.decode("utf-8"))
                    print(f"Server is up! Health: {data['status']}")
                    break
            except Exception:
                time.sleep(0.3)
        else:
            print("Server failed to respond within 10s")
            return 1

        # Test index.html
        code, body = get(url)
        text = body.decode("utf-8")
        assert code == 200
        assert "LoomShield" in text
        assert "auditInputStage" in text
        print("PASS: index.html served correctly")

        # Test static css and tokens
        code, body = get(f"{url}/static/styles.css")
        css_text = body.decode("utf-8")
        assert code == 200
        assert "--primary-action: #C84624" in css_text
        assert "InterVariable.woff2" in css_text
        assert "GeistMono-Variable.woff2" in css_text
        assert ".rq-doc-col" in css_text
        assert ".insights-stack" in css_text
        assert "del.diff-del" in css_text
        print("PASS: styles.css contains all required enterprise tokens and components")

        # Test fonts endpoint
        code1, f1 = get(f"{url}/fonts/InterVariable.woff2")
        assert code1 == 200 and len(f1) > 300000
        code2, f2 = get(f"{url}/fonts/GeistMono-Variable.woff2")
        assert code2 == 200 and len(f2) > 20000
        print(f"PASS: fonts served cleanly (Inter: {len(f1)} bytes, GeistMono: {len(f2)} bytes)")

        # Test session endpoint
        code, body = get(f"{url}/api/session")
        assert code == 200
        s_data = json.loads(body.decode("utf-8"))
        assert s_data["workspace_mode"] == "production"
        assert s_data["is_demo_mode"] is False
        assert s_data["user_role"] in ["Reviewer", "Brand Administrator", "Content Creator"]
        print(f"PASS: session endpoint returns {s_data['user_name']} ({s_data['user_role']})")

        # Test ambiguity radar
        code, body = get(f"{url}/api/ambiguity-radar/novapay")
        assert code == 200
        r_data = json.loads(body.decode("utf-8"))
        assert "rules_analysis" in r_data
        print(f"PASS: ambiguity radar returns {len(r_data['rules_analysis'])} analyzed rules")

        # Test engine status & selftest
        code, body = post(f"{url}/api/engine-selftest")
        assert code == 200
        st_data = json.loads(body.decode("utf-8"))
        assert st_data["self_test"]["passed"] is True
        print("PASS: engine selftest passed on-device")

        print("\nALL LIVE SERVER CHECKS PASSED!")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    sys.exit(main())
