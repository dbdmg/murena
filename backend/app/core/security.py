"""
Security utilities including password hashing and JWT token handling.
"""

from datetime import datetime, timedelta
from typing import Optional, Union, Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.

    Args:
        plain_password: The plain text password
        hashed_password: The hashed password from database

    Returns:
        bool: True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password for storage.

    Args:
        password: The plain text password

    Returns:
        str: The hashed password
    """
    return pwd_context.hash(password)


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        subject: The subject of the token (usually username or user_id)
        expires_delta: Optional expiration time

    Returns:
        str: Encoded JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.

    Args:
        subject: The subject of the token
        expires_delta: Optional expiration time

    Returns:
        str: Encoded JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.

    Args:
        token: The JWT token to decode

    Returns:
        dict: The decoded token payload

    Raises:
        jwt.JWTError: If token is invalid or expired
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
