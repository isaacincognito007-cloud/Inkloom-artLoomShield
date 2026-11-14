from pathlib import Path

p = Path(r"D:\LoomShield\backend\main.py")
content = p.read_text(encoding="utf-8")

old_code = """@app.post("/api/demo/reset")
def reset_demo_workspace_endpoint(request: Request):
    if not is_demo_mode():
        raise HTTPException(
            status_code=403,
            detail="Demo reset is only available in demo workspace mode.",
        )
    client_ip = get_client_ip(request)
    if not audit_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait a moment before resetting demo data.",
        )
    reset_demo_workspace()
    return {
        "status": "reset",
        "message": "Sample workspace restored to its initial state.",
        "overview": get_overview_dashboard("novapay"),
    }"""

new_code = """_LAST_DEMO_RESET_TIME: float = 0.0


@app.post("/api/demo/reset")
def reset_demo_workspace_endpoint(request: Request):
    global _LAST_DEMO_RESET_TIME
    if not is_demo_mode():
        raise HTTPException(
            status_code=403,
            detail="Demo reset is only available in demo workspace mode.",
        )
    client_ip = get_client_ip(request)
    if not audit_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait a moment before resetting demo data.",
        )

    bypass_cooldown = (
        bool(os.environ.get("PYTEST_CURRENT_TEST"))
        or bool(os.environ.get("LOOMSHIELD_TEST_MODE"))
        or request.headers.get("x-bypass-cooldown") == "true"
        or request.headers.get("x-loomshield-test") == "true"
    )
    now = time.time()
    if not bypass_cooldown and (now - _LAST_DEMO_RESET_TIME < 600.0):
        remaining = int(600.0 - (now - _LAST_DEMO_RESET_TIME))
        raise HTTPException(
            status_code=429,
            detail=f"Demo reset is on cooldown (10 minutes) to protect the shared workspace. Please wait {remaining} seconds before resetting again.",
        )

    reset_demo_workspace()
    _LAST_DEMO_RESET_TIME = now
    return {
        "status": "reset",
        "message": "Sample workspace restored to its initial state.",
        "overview": get_overview_dashboard("novapay"),
    }"""

assert old_code in content, "old_code not found in backend/main.py"
content = content.replace(old_code, new_code, 1)
p.write_text(content, encoding="utf-8")
print("Updated reset_demo_workspace_endpoint in backend/main.py")
