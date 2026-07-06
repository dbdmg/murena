"""
Database connection management using SQLAlchemy.

Provides:
- Database engine creation
- Session management
- Dependency injection for FastAPI
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.utils.logger import logger

# Create database engine
# pool_pre_ping=True ensures connections are checked before use
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine_kwargs = {
    "echo": settings.SQL_ECHO,
    "pool_pre_ping": True,
}

if is_sqlite:
    # SQLite-specific arguments
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Postgres/Standard arguments
    engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency function for FastAPI to get database session.

    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables and run migrations.

    Should be called once at application startup.
    """
    from app.database.models import Base
    from app.database.migrate_agent_feedback import run_migration

    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    
    # Run manual migrations for existing tables
    try:
        run_migration()
    except Exception as e:
        logger.error(f"Post-initialization migration failed: {e}")
        
    logger.info("Database initialized and migrated successfully")


def drop_db():
    """
    Drop all database tables.

    WARNING: This will delete all data!
    Use only for testing or development reset.
    """
    from app.database.models import Base

    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("All tables dropped")
