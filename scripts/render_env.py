#!/usr/bin/env python3
"""
Print the environment variables for a MedShield web service on Render.

    python scripts/render_env.py [--users-file users.json] [--full-resolution]

The first run creates deploy/render/secrets.env (git-ignored) with random secrets; later runs reuse
it, so pasting the output again does not change your keys. Paste the first block into the service's
Environment page ("Add from .env"), then add MEDSHIELD_USERS_JSON as its own variable: its bcrypt
hashes contain "$", which .env import would try to expand.

--full-resolution leaves out the low-memory settings (use on a plan with >= 2 GB RAM).
"""

import argparse
import json
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SECRETS_FILE = REPO_ROOT / "deploy" / "render" / "secrets.env"

BASE_VARS = {"MEDSHIELD_ENABLE_DEMO_USERS": "false"}

# Keeps the server under the free plan's 512 MB (measured peak ~475 MB with a 3000 x 3000 upload)
LOW_MEMORY_VARS = {
    "MEDSHIELD_MAX_IMAGE_DIM": "1024",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "MALLOC_ARENA_MAX": "2",
    "MALLOC_MMAP_THRESHOLD_": "131072",
    "MALLOC_TRIM_THRESHOLD_": "131072",
}


def load_or_create_secrets() -> dict:
    if not SECRETS_FILE.exists():
        SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SECRETS_FILE.write_text(
            "# Render secrets for MedShield. KEEP PRIVATE (git-ignored). Reused by scripts/render_env.py.\n"
            f"MEDSHIELD_SECRET_PEPPER={secrets.token_urlsafe(48)}\n"
            f"MEDSHIELD_JWT_SECRET_KEY={secrets.token_urlsafe(48)}\n"
        )
        SECRETS_FILE.chmod(0o600)
        print(f"Created {SECRETS_FILE.relative_to(REPO_ROOT)} with fresh random secrets.", file=sys.stderr)
    values = {}
    for line in SECRETS_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users-file", type=Path, help="accounts file from scripts/create_user.py")
    parser.add_argument("--full-resolution", action="store_true", help="omit low-memory settings (>= 2 GB plans)")
    args = parser.parse_args()

    env = {**load_or_create_secrets(), **BASE_VARS}
    if not args.full_resolution:
        env.update(LOW_MEMORY_VARS)

    print("\n# ---- 1. Paste into Render > your service > Environment > Add from .env ----")
    for key, value in env.items():
        print(f"{key}={value}")

    if args.users_file:
        users = json.loads(args.users_file.read_text())
        if not isinstance(users, list) or not users:
            sys.exit(f"{args.users_file} has no accounts; create one with scripts/create_user.py")
        print("\n# ---- 2. Add one more variable by hand ----")
        print("# Key:   MEDSHIELD_USERS_JSON")
        print("# Value (one line, keep it secret):")
        print(json.dumps(users, separators=(",", ":")))
    else:
        print("\n# No --users-file given: nobody can sign in until you add MEDSHIELD_USERS_JSON")
        print("# (python scripts/create_user.py ...) or set MEDSHIELD_ENABLE_DEMO_USERS=true.")


if __name__ == "__main__":
    main()
