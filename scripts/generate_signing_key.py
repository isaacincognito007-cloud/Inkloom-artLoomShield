#!/usr/bin/env python3
"""
Generate a 32-byte Ed25519 signing seed and public key for LoomShield Compliance Certificates.
Usage:
    python scripts/generate_signing_key.py
"""
import base64
import hashlib
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> None:
    seed = os.urandom(32)
    priv = Ed25519PrivateKey.from_private_bytes(seed)
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    seed_b64 = base64.b64encode(seed).decode("ascii")
    pub_b64 = base64.b64encode(pub_bytes).decode("ascii")
    kid = hashlib.sha256(pub_bytes).hexdigest()[:16]

    print(f"LOOMSHIELD_SIGNING_KEY={seed_b64}")
    print(f"PUBLIC_KEY_B64={pub_b64}")
    print(f"KID={kid}")


if __name__ == "__main__":
    main()
