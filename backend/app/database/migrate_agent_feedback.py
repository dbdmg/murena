"""
Database migration script to add agent feedback support and evaluation fields.
Compatible with both SQLite and PostgreSQL.
"""

import sys
import os
from sqlalchemy import text, inspect
from app.database.connection import engine
from app.utils.logger import logger

def run_migration():
    """Add missing columns to feedback table using SQLAlchemy engine."""
    logger.info("Starting database migration for feedback table...")
    
    # Columns to check and add if missing
    # Format: (column_name, sql_type)
    new_columns = [
        ("agent_name", "VARCHAR(255)"),
        ("user_id", "INTEGER"),
    ]
    
    try:
        with engine.connect() as conn:
            # Check existing columns using SQLAlchemy inspector
            inspector = inspect(engine)
            existing_columns = [col["name"] for col in inspector.get_columns("feedback")]
            
            applied = []
            for col_name, col_type in new_columns:
                if col_name not in existing_columns:
                    logger.info(f"Adding column {col_name} to feedback table...")
                    # SQLAlchemy doesn't have a cross-DB 'ADD COLUMN' abstraction in core
                    # so we use a simple ALTER TABLE which is standard for SQLite/Postgres
                    conn.execute(text(f"ALTER TABLE feedback ADD COLUMN {col_name} {col_type}"))
                    applied.append(col_name)
            
            # Special case: add foreign key for user_id on PostgreSQL if possible
            # (Skipping index creation as it's DB specific and less critical than columns)
            
            conn.commit()
            
            if applied:
                logger.info(f"✓ Migration completed! Added: {', '.join(applied)}")
            else:
                logger.info("✓ No migration needed - all columns exist")
            
            return True
            
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}")
        return False


if __name__ == "__main__":
    # Ensure we can import app if running as script
    sys.path.append(os.getcwd())
    
    success = run_migration()
    sys.exit(0 if success else 1)
