#!/usr/bin/env python3
"""
Offline CLI Verifier for LoomShield Ed25519 Signed Compliance Certificates.
Usage:
    python scripts/verify_certificate.py cert.json --public-key <b64>
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.certificates import verify_certificate_envelope


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a LoomShield Ed25519 Compliance Certificate offline.")
    parser.add_argument("certificate_file", help="Path to the certificate JSON file")
    parser.add_argument("--public-key", required=True, dest="public_key_b64", help="Base64-encoded 32-byte Ed25519 public key")
    args = parser.parse_args()

    try:
        with open(args.certificate_file, "r", encoding="utf-8") as f:
            envelope = json.load(f)
    except Exception as exc:
        print(f"INVALID: Could not parse JSON from '{args.certificate_file}': {exc}")
        return 1

    result = verify_certificate_envelope(envelope, public_key_b64=args.public_key_b64)
    if result.get("valid"):
        print(
            f"VALID: Certificate '{result.get('certificate_id')}' for audit '{result.get('audit_id')}' "
            f"(content_sha256={result.get('content_sha256')}, kid={result.get('kid')})."
        )
        if result.get("ephemeral_key"):
            print(f"NOTICE: {result.get('key_notice')}")
        return 0

    reasons = "; ".join(result.get("reasons") or ["Verification failed."])
    print(f"INVALID ({result.get('status', 'invalid')}): {reasons}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
