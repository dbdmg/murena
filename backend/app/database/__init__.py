"""Database package for the FastAPI backend.

This backend uses SQLAlchemy (see app.database.connection + app.database.models).
Legacy Flask/sqlite helpers from the Dash monolith are intentionally not exposed here.
"""

from app.database.connection import get_db, init_db

__all__ = ["get_db", "init_db"]
