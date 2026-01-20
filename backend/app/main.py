"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.api.v1.router import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the application.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {'Development' if settings.DEBUG else 'Production'}")

    # Initialize Database
    try:
        from app.database.connection import init_db, SessionLocal
        from app.repositories import UserRepository
        from app.core import security

        init_db()
        logger.info("Database initialized")

        # Create default admin user
        db = SessionLocal()
        try:
            user_repo = UserRepository(db)
            if not user_repo.get_by_username("admin"):
                user_repo.create_user(
                    username="admin",
                    password_hash=security.get_password_hash("admin123"),
                    email="admin@mef-immobili.it",
                )
                logger.info("Default admin user created")
        except Exception as e:
            logger.error(f"Error creating admin user: {e}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="RESTful API for MEF-Immobili real estate analysis platform",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
