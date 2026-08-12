"""Credential helper for external review-admin configuration."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from typing import Sequence

from .auth import AdminAuthError, hash_password


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    hashing = commands.add_parser("hash-password", help="create one scrypt password hash for IMAGE2_ADMIN_USERS_JSON")
    hashing.add_argument("--password-stdin", action="store_true")
    hashing.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command != "hash-password":
            raise AssertionError("unsupported command")
        password = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else getpass.getpass("Admin password: ")
        encoded = hash_password(password)
        if args.json:
            print(json.dumps({"status": "ok", "password_hash": encoded}, sort_keys=True))
        else:
            print(encoded)
        return 0
    except AdminAuthError as exc:
        payload = {"status": "failed", "error_code": exc.error_code, "message": str(exc)}
        print(json.dumps(payload, sort_keys=True) if getattr(args, "json", False) else str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
