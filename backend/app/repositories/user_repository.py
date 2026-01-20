"""
User repository for user account operations.
"""

from typing import Optional
from sqlalchemy.orm import Session

from app.database.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""

    def __init__(self, db: Session):
        """Initialize with User model."""
        super().__init__(User, db)

    def get_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            username: Username to search for

        Returns:
            User instance or None if not found
        """
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            email: Email address to search for

        Returns:
            User instance or None if not found
        """
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, username: str, password_hash: str, email: Optional[str] = None) -> User:
        """
        Create a new user.

        Args:
            username: Unique username
            password_hash: Hashed password
            email: Optional email address

        Returns:
            Created User instance
        """
        user = User(username=username, password_hash=password_hash, email=email)
        return self.create(user)

    def verify_unique_username(self, username: str) -> bool:
        """
        Check if username is available.

        Args:
            username: Username to check

        Returns:
            True if username is available, False if taken
        """
        return self.get_by_username(username) is None

    def verify_unique_email(self, email: str) -> bool:
        """
        Check if email is available.

        Args:
            email: Email to check

        Returns:
            True if email is available, False if taken
        """
        if not email:
            return True
        return self.get_by_email(email) is None
