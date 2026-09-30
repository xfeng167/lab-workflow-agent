"""Interactive local credential setup; separate from the read-only agent."""
import getpass
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import warnings

import httpx
from dotenv import set_key

ROOT = Path(__file__).resolve().parents[1]


class SetupError(Exception):
    pass


def check_destination(root: Path) -> None:
    destination = root / ".env"
    if destination.is_symlink() or (destination.exists() and not destination.is_file()):
        raise SetupError("The .env destination must be a regular local file.")
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", ".env"], cwd=root,
                             capture_output=True)
    ignored = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=root,
                             capture_output=True)
    if tracked.returncode == 0 or ignored.returncode != 0:
        raise SetupError("Stop: .env must be untracked and ignored by Git before saving a token.")


def login(username: str, password: str, *, transport=None) -> str:
    try:
        with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10,
                          follow_redirects=False, trust_env=False,
                          transport=transport if transport is not None else httpx.HTTPTransport(retries=0)) as client:
            response = client.post("/users/login", json={"username": username, "password": password})
    except httpx.HTTPError:
        raise SetupError("Cannot reach the local Lab Storage API. Check that it is running; no retry was made.") from None
    if response.status_code != 200:
        messages = {401: "Login failed. Check your local Lab Storage username and password.",
                    429: "Login rate limit reached. Wait before trying again."}
        raise SetupError(messages.get(response.status_code, "Local login failed; no retry was made."))
    try:
        token = response.json()["token"]
        if not isinstance(token, str) or not token or len(token) > 512 or not token.isascii() or any(
                char.isspace() or ord(char) < 33 or ord(char) == 127 for char in token):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise SetupError("Local login returned an invalid token response.") from None
    return token


def save_token(root: Path, token: str) -> None:
    check_destination(root)
    destination = root / ".env"
    previous = destination.read_text() if destination.exists() else ""
    fd, temporary = tempfile.mkstemp(prefix=".local-token-", dir=root)
    try:
        with os.fdopen(fd, "w") as output:
            output.write(previous)
        set_key(temporary, "LAB_STORAGE_BEARER_TOKEN", token)
        set_key(temporary, "LAB_STORAGE_API_URL", "http://127.0.0.1:8000")
        # mkstemp creates mode 0600: only the current user can read/write it.
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    logging.disable(logging.CRITICAL)
    try:
        check_destination(ROOT)
        if not sys.stdin.isatty():
            raise SetupError("Run this helper in your own interactive terminal.")
        print("Local Lab Storage login: http://127.0.0.1:8000 (not your Moonshot account)")
        username = input("Username: ").strip()
        # Refuse getpass's visible-input fallback.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Password (hidden): ")
        if not username or not password:
            raise SetupError("Username and password are required.")
        token = login(username, password)
        save_token(ROOT, token)
        print("Token saved privately to .env. Token value was not printed.")
        print("Run: unset LAB_STORAGE_BEARER_TOKEN; uv run labops-agent doctor")
        return 0
    except SetupError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("Setup cancelled.", file=sys.stderr)
        return 130
    except (OSError, UnicodeError, getpass.GetPassWarning):
        print("Could not safely complete setup. Check terminal and file permissions.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
