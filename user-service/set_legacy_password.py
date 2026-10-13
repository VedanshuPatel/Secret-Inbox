"""Set an initial password for a legacy local account before public exposure."""

from getpass import getpass

from database import SessionLocal
from services import UserService


def main() -> None:
    username = input("Legacy account username: ")
    password = getpass("New password (at least 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    if not 12 <= len(password) <= 128:
        raise SystemExit("Password must be between 12 and 128 characters.")

    db = SessionLocal()
    try:
        UserService.set_legacy_password(db, username, password)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    finally:
        db.close()
    print("Password set. You can now sign in with this account.")


if __name__ == "__main__":
    main()
