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

    # Preload dataset and indexed cache for fast first request
    try:
        import asyncio
        from app.services.real_estate_service import RealEstateService
        from app.data.loaders import load_and_merge_data

        dataset_path = settings.dataset_options.get("full")
        if dataset_path:
            logger.info(f"Preloading dataset from {dataset_path}...")

            # Load dataset
            df = load_and_merge_data(dataset_path)
            RealEstateService._dataset_cache["full"] = df
            logger.info(f"Dataset preloaded: {len(df)} rows")

            # Build indexed cache for O(1) lookups (same format as _load_dataset)
            if "id" in df.columns:
                logger.info("Building indexed cache...")
                df_indexed = df.copy()
                df_indexed["id_str"] = df_indexed["id"].astype(str)
                df_indexed = df_indexed.drop_duplicates(subset=["id_str"])
                df_indexed.set_index("id_str", inplace=True)
                RealEstateService._dataset_indexed_cache["full"] = df_indexed
                logger.info(f"Indexed cache ready: {len(df_indexed)} entries")

            # Update database metadata dynamically
            try:
                from app.data.metadata_manager import MetadataManager
                meta_manager = MetadataManager()
                meta_manager.update_metadata(df)
            except Exception as e:
                logger.warning(f"Metadata update failed: {e}")
    except Exception as e:
        logger.warning(f"Dataset preloading failed (will load on first request): {e}")

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
    import argparse

    # Parsing argomenti command line
    parser = argparse.ArgumentParser(description=f"Avvia il server {settings.APP_NAME}")
    parser.add_argument(
        "--model", 
        choices=["gpt-oss-120b", "deepseek-r1-8b", "vllm-gemma3-27b", "vllm-deepseek", "gpt-5-nano"], 
        help="Scegli il sapore del modello LLM da utilizzare"
    )
    
    # parse_known_args permette di ignorare gli argomenti di uvicorn se presenti
    args, _ = parser.parse_known_args()

    # Applica configurazione modello se specificata
    if args.model:
        settings.set_llm_model(args.model)
        logger.info(f"Modello LLM impostato a: {args.model} ({settings.OPENAI_MODEL_FAST})")

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
