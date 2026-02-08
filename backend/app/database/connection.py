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
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG,  # Log SQL queries in debug mode
)

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
