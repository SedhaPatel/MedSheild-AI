#!/usr/bin/env python3
"""
Deploy MedShield to a Hugging Face Docker Space.

  1. pip install huggingface_hub   and   hf auth login   (paste a token with "write" access)
  2. python scripts/deploy_hf_space.py --init-secrets            # creates deploy/huggingface/space-secrets.env
  3. python scripts/create_user.py --username ... --role ...     # real accounts -> users.json (optional)
  4. python scripts/deploy_hf_space.py <hf-user>/<space-name> [--users-file users.json]

Only files committed to git are uploaded (no .env, users.json, keys or local studies). The Space's
README is replaced with deploy/huggingface/README.md, which tells Hugging Face to build the Dockerfile.
"""

import argparse
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECRETS_FILE = REPO_ROOT / "deploy" / "huggingface" / "space-secrets.env"
SPACE_CARD = REPO_ROOT / "deploy" / "huggingface" / "README.md"

# Files the Docker build needs; everything else (tests, docs, scripts) stays out of the Space
UPLOAD_PATTERNS = [
    "Dockerfile", ".dockerignore", "requirements-prod.txt", "pyproject.toml", "README.md",
    "medshield/**", "frontend/**", "test_samples/**",
]
# Stored as Space *secrets* (hidden); any other KEY=VALUE becomes a public Space *variable*
SECRET_KEYS = {
    "MEDSHIELD_SECRET_PEPPER", "MEDSHIELD_JWT_SECRET_KEY", "MEDSHIELD_USERS_JSON",
    "GEMINI_API_KEY", "HF_API_TOKEN", "MEDSHIELD_TRUSTED_PROXY_SECRET",
}

SECRETS_TEMPLATE = """# Hugging Face Space settings for MedShield. KEEP THIS FILE PRIVATE (it is git-ignored).
# Uploaded by scripts/deploy_hf_space.py: keys in SECRET_KEYS become hidden secrets, others plain variables.

# Required: unique random values (generated for you)
MEDSHIELD_SECRET_PEPPER={pepper}
MEDSHIELD_JWT_SECRET_KEY={jwt}

# Sign-in accounts. Either pass --users-file users.json (from scripts/create_user.py),
# or set MEDSHIELD_ENABLE_DEMO_USERS=true to allow the published demo logins (anyone could sign in as admin).
MEDSHIELD_ENABLE_DEMO_USERS=false

# Optional: session length in minutes
MEDSHIELD_JWT_EXPIRE_MINUTES=60

# Optional: external model for the chat assistant (otherwise the built-in assistant answers)
# MEDSHIELD_CHAT_PROVIDER=gemini
# GEMINI_API_KEY=
"""


def init_secrets(path: Path) -> None:
    if path.exists():
        sys.exit(f"{path} already exists; edit it instead of regenerating (that would change your keys).")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SECRETS_TEMPLATE.format(pepper=secrets.token_urlsafe(48), jwt=secrets.token_urlsafe(48)))
    path.chmod(0o600)
    print(f"Created {path} with fresh random secrets. Review it, then run the deploy command.")


def read_settings(path: Path) -> dict:
    values = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.strip():
            values[key.strip()] = value.strip()
    return values


def check_settings(values: dict) -> None:
    problems = []
    for key in ("MEDSHIELD_SECRET_PEPPER", "MEDSHIELD_JWT_SECRET_KEY"):
        if len(values.get(key, "")) < 32:
            problems.append(f"{key} must be set to at least 32 characters")
    demo = values.get("MEDSHIELD_ENABLE_DEMO_USERS", "false").lower() in ("1", "true", "yes")
    if not values.get("MEDSHIELD_USERS_JSON") and not demo:
        problems.append("no accounts: pass --users-file users.json or set MEDSHIELD_ENABLE_DEMO_USERS=true")
    if problems:
        sys.exit("Settings problem(s):\n  - " + "\n  - ".join(problems))


def export_committed_tree(dest: Path) -> str:
    """Extracts git HEAD (committed files only) into dest; returns the short commit hash."""
    status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    if status.stdout.strip():
        print("Note: you have uncommitted changes; only committed files are deployed.", file=sys.stderr)
    archive = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=REPO_ROOT, capture_output=True, check=True)
    with tarfile.open(fileobj=BytesIO(archive.stdout)) as tar:
        tar.extractall(dest, filter="data")
    shutil.copyfile(SPACE_CARD, dest / "README.md")
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("space", nargs="?", help="Space id, e.g. your-hf-username/medshield")
    parser.add_argument("--init-secrets", action="store_true", help="create the private settings file with random secrets")
    parser.add_argument("--secrets-file", type=Path, default=DEFAULT_SECRETS_FILE)
    parser.add_argument("--users-file", type=Path, help="users.json from scripts/create_user.py")
    parser.add_argument("--private", action="store_true", help="create the Space as private")
    parser.add_argument("--skip-settings", action="store_true", help="upload code only; leave Space settings unchanged")
    args = parser.parse_args()

    if args.init_secrets:
        init_secrets(args.secrets_file)
        return
    if not args.space or "/" not in args.space:
        parser.error("give the Space id as <hf-username>/<space-name>")

    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("Install the Hugging Face client first: pip install huggingface_hub")

    api = HfApi()
    try:
        who = api.whoami()["name"]
    except Exception:
        sys.exit("Not logged in to Hugging Face. Run `hf auth login` with a token that has write access.")
    print(f"Logged in to Hugging Face as {who}")

    values = {}
    if not args.skip_settings:
        if not args.secrets_file.exists():
            sys.exit(f"{args.secrets_file} not found. Run: python scripts/deploy_hf_space.py --init-secrets")
        values = read_settings(args.secrets_file)
        if args.users_file:
            import json
            try:
                users = json.loads(Path(args.users_file).read_text())
            except (OSError, ValueError) as exc:
                sys.exit(f"Could not read {args.users_file}: {exc}")
            if not isinstance(users, list) or not users:
                sys.exit(f"{args.users_file} has no accounts; create some with scripts/create_user.py")
            values["MEDSHIELD_USERS_JSON"] = json.dumps(users, separators=(",", ":"))
        check_settings(values)

    api.create_repo(args.space, repo_type="space", space_sdk="docker", private=args.private, exist_ok=True)

    for key, value in values.items():
        if key in SECRET_KEYS:
            api.add_space_secret(args.space, key, value)
        else:
            api.add_space_variable(args.space, key, value)
    if values:
        print(f"Set {sum(k in SECRET_KEYS for k in values)} secret(s) and {sum(k not in SECRET_KEYS for k in values)} variable(s).")

    with tempfile.TemporaryDirectory() as tmp:
        commit = export_committed_tree(Path(tmp))
        api.upload_folder(
            folder_path=tmp,
            repo_id=args.space,
            repo_type="space",
            allow_patterns=UPLOAD_PATTERNS,
            delete_patterns=["*"],          # the Space mirrors this commit exactly
            commit_message=f"Deploy MedShield {commit}",
        )

    print(f"Uploaded commit {commit}. Hugging Face is now building the Docker image (about 10-15 minutes).")
    print(f"Follow the build and open the app at: https://huggingface.co/spaces/{args.space}")


if __name__ == "__main__":
    main()
