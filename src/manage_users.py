"""Provision a practice lead or consultant account with a hashed password."""

import argparse
from getpass import getpass

try:
    from .auth import create_user
except ImportError:
    from auth import create_user


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("role", choices=["practice_lead", "consultant"])
    parser.add_argument(
        "--practice-areas",
        default="",
        help="Comma-separated practice areas for a lead; use * to grant all areas",
    )
    args = parser.parse_args()
    password = getpass("Password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Passwords do not match")
    areas = [area.strip() for area in args.practice_areas.split(",") if area.strip()]
    try:
        user = create_user(args.email, password, args.role, areas)
    except ValueError as error:
        parser.error(str(error))
    print(f"Created {user['role']} account for {user['email']}")


if __name__ == "__main__":
    main()