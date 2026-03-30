"""
Initialization logic for the FastAPI application.
Handles database setup, seed data, and dataset preloading.
"""

import logging
from fastapi import FastAPI
from app.core.config import settings
from app.database.connection import init_db, SessionLocal
from app.repositories.user_repository import UserRepository
from app.core import security
from app.services.real_estate_service import RealEstateService
from app.data.loaders import load_and_merge_data
from app.data.metadata_manager import MetadataManager

logger = logging.getLogger(__name__)

def initialize_database():
    """Initialize database and create default admin user."""
    try:
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
                    email="admin@realestate-ai.example",
                )
                logger.info("Default admin user created")
        except Exception as e:
            logger.error(f"Error creating admin user: {e}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

def preload_datasets():
    """Preload datasets and build indexed caches."""
    try:
        dataset_path = settings.dataset_options.get("full")
        if dataset_path:
            logger.info(f"Preloading dataset from {dataset_path}...")

            # Load dataset
            df = load_and_merge_data(dataset_path)
            
            if df is not None:
                RealEstateService._dataset_cache["full"] = df
                logger.info(f"Dataset preloaded: {len(df)} rows")

                # Build indexed cache for O(1) lookups
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
                    meta_manager = MetadataManager()
                    meta_manager.update_metadata(df)
                except Exception as e:
                    logger.warning(f"Metadata update failed: {e}")
            else:
                logger.warning(f"Dataset at {dataset_path} could not be loaded")
    except Exception as e:
        logger.warning(f"Dataset preloading failed (will load on first request): {e}")

async def startup_event():
    """Centralized startup event handler."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {'Development' if settings.DEBUG else 'Production'}")
    
    initialize_database()
    preload_datasets()

async def shutdown_event():
    """Centralized shutdown event handler."""
    logger.info("Shutting down application...")
