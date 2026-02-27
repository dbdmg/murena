"""
MEF-Immobili User Deletion Script

Deletes a user from the database by username.

Usage:
    cd backend
    python delete_user.py
"""

import sys
from pathlib import Path

# Add current directory to path so we can import app modules
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

from app.database.connection import SessionLocal
from app.repositories import UserRepository


def main():
    print("=== MEF-Immobili User Deletion ===")
    print("This script removes a user from the database.\n")

    # 1. Gather Input
    username = input("Username to delete: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        return

    # 2. Database Operation
    db = SessionLocal()
    try:
        repo = UserRepository(db)

        # Find user
        user = repo.get_by_username(username)
        if not user:
            print(f"Error: User '{username}' not found.")
            return

        # Show user info
        print(f"\nUser found:")
        print(f"  ID:       {user.id}")
        print(f"  Username: {user.username}")
        print(f"  Email:    {user.email or 'N/A'}")

        # Confirm deletion
        confirm = (
            input(f"\nAre you sure you want to delete '{username}'? (yes/no): ")
            .strip()
            .lower()
        )
        if confirm != "yes":
            print("Deletion cancelled.")
            return

        # Delete user
        repo.delete(user.id)
        print(f"\n User '{username}' has been deleted.")

    except Exception as e:
        print(f" An error occurred: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
