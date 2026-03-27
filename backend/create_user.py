import sys
import os
from pathlib import Path

# Add current directory to path so we can import app modules
# This allows running the script from the backend directory
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

from getpass import getpass
from app.database.connection import SessionLocal
from app.repositories import UserRepository
from app.core.security import get_password_hash


def main():
    print("=== RealEstate-AI User Creator ===")
    print("This script adds a new user to the database.\n")

    # 1. Gather Input
    username = input("Username: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        return

    email = input("Email: ").strip()
    if not email:
        print("Error: Email cannot be empty.")
        return

    password = getpass("Password: ")
    if not password:
        print("Error: Password cannot be empty.")
        return

    confirm_password = getpass("Confirm Password: ")
    if password != confirm_password:
        print("Error: Passwords do not match.")
        return

    print(f"\nCreating user '{username}'...")

    # 2. Database Operation
    db = SessionLocal()
    try:
        repo = UserRepository(db)

        # Check uniqueness
        if not repo.verify_unique_username(username):
            print(f"Error: Username '{username}' is already taken.")
            return

        if not repo.verify_unique_email(email):
            print(f"Error: Email '{email}' is already taken.")
            return

        # Create user
        hashed_password = get_password_hash(password)
        user = repo.create_user(
            username=username, password_hash=hashed_password, email=email
        )

        print(f" Success! User created with ID: {user.id}")
        print(f"You can now log in as '{username}'.")

    except Exception as e:
        print(f" An error occurred: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
