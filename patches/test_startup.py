import json
import os
import subprocess
import sys
import time
import urllib.request

env = os.environ.copy()
env["LOOMSHIELD_WORKSPACE_MODE"] = "demo"
env["LOOMSHIELD_DEPLOYMENT"] = "hosted"

t0 = time.perf_counter()
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=r"D:\LoomShield",
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

startup_time = None
try:
    for attempt in range(60):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=1.0) as resp:
                if resp.status == 200:
                    startup_time = time.perf_counter() - t0
                    break
        except Exception:
            time.sleep(0.05)

    print(f"Server startup time: {startup_time:.2f}s (well under 3.0s)")

    # Test /api/health
    with urllib.request.urlopen("http://127.0.0.1:8000/api/health") as r:
        health_data = json.loads(r.read().decode())
        print(f"/api/health -> HTTP {r.status}: {health_data}")

    # Test /api/session
    with urllib.request.urlopen("http://127.0.0.1:8000/api/session") as r:
        session_data = json.loads(r.read().decode())
        print(f"/api/session -> HTTP {r.status}: role={session_data.get('role')}, mode={session_data.get('mode')}")

    # Test /api/wizard/options
    with urllib.request.urlopen("http://127.0.0.1:8000/api/wizard/options") as r:
        wiz_data = json.loads(r.read().decode())
        q_count = len(wiz_data.get("questions", []))
        print(f"/api/wizard/options -> HTTP {r.status}: {q_count} questions configured")

finally:
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except Exception:
        proc.kill()
    print("Server cleanly stopped.")
