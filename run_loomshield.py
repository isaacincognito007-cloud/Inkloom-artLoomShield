import argparse
import os
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LoomShield Brand Governance Platform")
    parser.add_argument("--demo", action="store_true", help="Launch in isolated sample demonstration mode")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    args = parser.parse_args()

    os.environ.setdefault("LOOMSHIELD_DEPLOYMENT", "local")

    if args.demo:
        os.environ["LOOMSHIELD_WORKSPACE_MODE"] = "demo"

    mode = (
        "Sample Demonstration Workspace"
        if os.environ.get("LOOMSHIELD_WORKSPACE_MODE") == "demo"
        else "Production Workspace"
    )
    print("=" * 72)
    print(f"  LoomShield Brand Governance Workspace ({mode})")
    print(f"  Workspace URL: http://{args.host}:{args.port}")
    print(f"  API Documentation: http://{args.host}:{args.port}/docs")
    print("=" * 72)
    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=False)
