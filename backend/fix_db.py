import sys
import os
from sqlalchemy import text
from app.database.connection import engine

# Ensure we can import app modules
sys.path.append(os.getcwd())

def fix_columns():
    print("Starting database column fix for PostgreSQL...")
    with engine.connect() as conn:
        # 1. Add agent_name
        try:
            print("Attempting to add agent_name column...")
            conn.execute(text("ALTER TABLE feedback ADD COLUMN IF NOT EXISTS agent_name VARCHAR(255);"))
            print("Success (or already existed).")
        except Exception as e:
            print(f"Error adding agent_name: {e}")

        # 2. Add user_id
        try:
            print("Attempting to add user_id column...")
            conn.execute(text("ALTER TABLE feedback ADD COLUMN IF NOT EXISTS user_id INTEGER;"))
            print("Success (or already existed).")
        except Exception as e:
             print(f"Error adding user_id: {e}")
             
        # 3. Add FK constraint for user_id (optional, but good to have)
        # Checking if constraint exists is harder in raw SQL without querying catalog.
        # simpler to just try adding it and ignore if fails, or skip it for now as the app logic handles it.
        # Let's stick to columns for now to fix the crash.

        conn.commit()
    
    print("Column fix completed.")

if __name__ == "__main__":
    fix_columns()
