from __future__ import annotations

import argparse
import getpass

from .config import Config
from .db import init_db
from .repository import Repository


def main() -> None:
    parser = argparse.ArgumentParser(description="Local job application assistant")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    create_user = sub.add_parser("create-user")
    create_user.add_argument("username")
    create_user.add_argument("email")
    args = parser.parse_args()

    if args.command == "init-db":
        init_db(Config.DATABASE)
        print(f"Initialized database at {Config.DATABASE}")
    elif args.command == "create-user":
        password = getpass.getpass("Password, at least 12 characters: ")
        repo = Repository(Config.DATABASE)
        user_id = repo.create_user(args.username, args.email, password)
        print(f"Created user {args.username} with id {user_id}")


if __name__ == "__main__":
    main()

