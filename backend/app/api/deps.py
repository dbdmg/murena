"""
API dependencies for dependency injection.
"""

from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    OAuth2PasswordBearer,
    HTTPBearer,
    HTTPAuthorizationCredentials,
)
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token
from app.database.connection import get_db
from app.database.models import User
from app.repositories import UserRepository

# OAuth2 scheme for Swagger UI compatibility
# This expects the /login endpoint to be at /api/v1/auth/login
reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"/api/v1/auth/login")

# HTTP Bearer for standard API clients
security = HTTPBearer()


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.

    Validates the token and retrieves user from database.
    """
    try:
        payload = decode_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = UserRepository(db).get_by_username(username=username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to get the current active user.
    Can be used to check if user is active/banned (if added in future).
    """
    return current_user


def get_current_user_optional(
    db: Session = Depends(get_db),
    # Use Security with auto_error=False for optional auth
    token_auth: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[User]:
    """
    Dependency for optional authentication.
    Returns User if valid token provided, else None.
    """
    if not token_auth:
        return None

    try:
        token = token_auth.credentials
        payload = decode_token(token)
        username: str = payload.get("sub")
        if not username:
            return None

        return UserRepository(db).get_by_username(username=username)
    except Exception:
        return None
