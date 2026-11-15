#!/usr/bin/env python3
"""
Create or update a MedShield user account for MEDSHIELD_USERS_JSON.

Passwords are read without echo and stored only as bcrypt hashes. Accounts are kept in a local
JSON file (default: users.json, git-ignored); paste its one-line contents into the
MEDSHIELD_USERS_JSON secret of your deployment.

Usage:
    python scripts/create_user.py --username dr_patel --role clinician \
        --full-name "Dr. A. Patel" --email a.patel@example.org
    python scripts/create_user.py --show          # print the JSON to paste into the secret

Roles: clinician (upload and read own studies), privacy_officer (audit and erase studies),
admin (everything).
"""

import argparse
import getpass
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from medshield.auth.models import ALL_ROLES  # noqa: E402
from medshield.auth.security import hash_password  # noqa: E402

MIN_PASSWORD_LENGTH = 12


def load(path: Path) -> list:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise SystemExit(f"{path} must contain a JSON list of users")
    return data


def read_password(username: str) -> str:
    while True:
        first = getpass.getpass(f"Password for {username}: ")
        if len(first) < MIN_PASSWORD_LENGTH:
            print(f"Use at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
            continue
        if first != getpass.getpass("Repeat password: "):
            print("Passwords did not match, try again.", file=sys.stderr)
            continue
        return first


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", default="users.json", type=Path, help="local accounts file (default: users.json)")
    parser.add_argument("--username")
    parser.add_argument("--role", choices=ALL_ROLES)
    parser.add_argument("--full-name")
    parser.add_argument("--email")
    parser.add_argument("--disable", action="store_true", help="disable this account instead of creating it")
    parser.add_argument("--show", action="store_true", help="print the one-line JSON for MEDSHIELD_USERS_JSON")
    args = parser.parse_args()

    users = load(args.file)

    if args.username:
        username = args.username.strip().lower()
        if not re.fullmatch(r"[a-z0-9_.-]{3,64}", username):
            raise SystemExit("Username: 3-64 characters, letters, digits, '.', '_' or '-'.")
        existing = next((u for u in users if u["username"] == username), None)
        if args.disable:
            if not existing:
                raise SystemExit(f"No account named {username} in {args.file}")
            existing["disabled"] = True
        else:
            if not (args.role and args.full_name and args.email):
                raise SystemExit("--role, --full-name and --email are required when creating an account")
            record = {
                "username": username,
                "email": args.email,
                "full_name": args.full_name,
                "role": args.role,
                "hashed_password": hash_password(read_password(username)),
                "disabled": False,
                "assigned_study_uids": [],
            }
            users = [u for u in users if u["username"] != username] + [record]
        args.file.write_text(json.dumps(users, indent=2) + "\n")
        print(f"Saved {username} to {args.file} ({len(users)} account(s)).", file=sys.stderr)

    if args.show or args.username:
        print("\nValue for MEDSHIELD_USERS_JSON (keep it secret; it contains password hashes):", file=sys.stderr)
        print(json.dumps(users, separators=(",", ":")))


if __name__ == "__main__":
    main()
