"""
Database migration script to add agent feedback support.

Run this with: python -m app.database.migrate_agent_feedback
"""

import sqlite3
import sys
import os
from pathlib import Path
from app.core.config import settings

def run_migration(db_path: str = None):
    """Add agent_name and user_id columns to feedback table."""
    if db_path is None:
        # Extract path from DATABASE_URL (sqlite:///./test.db -> ./test.db)
        if settings.DATABASE_URL.startswith("sqlite:///"):
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            # Handle absolute paths vs relative
            if db_path.startswith("./"):
                # Path relative to backend root
                db_path = os.path.join(os.getcwd(), db_path[2:])
        else:
            print("Auto-migration only supported for SQLite.")
            return True

    print(f"Running migration on database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(feedback)")
        columns = [row[1] for row in cursor.fetchall()]
        
        migrations_applied = []
        
        # Add agent_name column if it doesn't exist
        if "agent_name" not in columns:
            print("Adding agent_name column...")
            cursor.execute("""
                ALTER TABLE feedback 
                ADD COLUMN agent_name VARCHAR(255)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_agent_name 
                ON feedback(agent_name)
            """)
            migrations_applied.append("agent_name")
        
        # Add user_id column if it doesn't exist
        if "user_id" not in columns:
            print("Adding user_id column...")
            cursor.execute("""
                ALTER TABLE feedback 
                ADD COLUMN user_id INTEGER REFERENCES users(id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_user_id 
                ON feedback(user_id)
            """)
            migrations_applied.append("user_id")
        
        conn.commit()
        
        if migrations_applied:
            print(f"✓ Migration completed successfully! Applied: {', '.join(migrations_applied)}")
        else:
            print("✓ No migration needed - columns already exist")
        
        return True
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    # If a path is provided as argument, use it. Otherwise, autodetect from settings.
    custom_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Ensure we can import app if running as script
    sys.path.append(os.getcwd())
    
    success = run_migration(custom_path)
    sys.exit(0 if success else 1)
