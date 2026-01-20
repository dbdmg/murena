"""
Authentication endpoints.
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api import deps
from app.core import security
from app.core.config import settings
from app.database.models import User
from app.models.requests import LoginRequest, RegisterRequest
from app.models.responses import TokenResponse, UserResponse
from app.repositories import UserRepository

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login_access_token(
    db: Session = Depends(deps.get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    user_repo = UserRepository(db)
    user = user_repo.get_by_username(form_data.username)

    if not user or not security.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        user.username, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/register", response_model=UserResponse)
def register_user(
    *,
    db: Session = Depends(deps.get_db),
    user_in: RegisterRequest,
) -> Any:
    """
    Create new user.
    """
    user_repo = UserRepository(db)

    if not user_repo.verify_unique_username(user_in.username):
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system",
        )

    if user_in.email and not user_repo.verify_unique_email(user_in.email):
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )

    user = user_repo.create_user(
        username=user_in.username,
        password_hash=security.get_password_hash(user_in.password),
        email=user_in.email,
    )

    return user


@router.get("/me", response_model=UserResponse)
def read_users_me(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    return current_user


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Refresh access token.
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        current_user.username, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
