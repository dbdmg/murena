import os
import sys
import subprocess
import argparse
import time
import shutil
from pathlib import Path
from getpass import getpass
from dotenv import load_dotenv

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent
root_dir = backend_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Load environment variables
load_dotenv(backend_dir / ".env")

def check_prerequisites():
    """Check if basic requirements are met."""
    if not (backend_dir / ".env").exists():
        print("Error: .env file not found in backend directory.")
        print("Please create it from .env.example first.")
        sys.exit(1)

def init_data():
    """Initialize datasets if they are missing."""
    metadata_dir = backend_dir / "data" / "metadata"
    data_path = metadata_dir / "estates.parquet"
    
    if not data_path.exists():
        print("Dataset not found or incomplete. Starting initialization...")
        
        create_estate_dataset = metadata_dir / "create_estate_dataset.py"
        create_pois = metadata_dir / "pois_download.py"
        
        # Get POI path from env
        poi_path_str = os.getenv("POI_PATH", "data/metadata/pois_by_category.json")
        poi_path = Path(poi_path_str)
        if not poi_path.is_absolute():
            if poi_path_str.startswith("backend/"):
                poi_path = backend_dir.parent / poi_path
            else:
                poi_path = backend_dir / poi_path
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(backend_dir)

        if not poi_path.exists() and create_pois.exists():
            print(f"[*] Running {create_pois.name}...")
            subprocess.run([sys.executable, str(create_pois)], cwd=str(backend_dir), env=env, check=True)

        if not data_path.exists() and create_estate_dataset.exists():
            print(f"[*] Running {create_estate_dataset.name}...")
            subprocess.run([sys.executable, str(create_estate_dataset)], cwd=str(backend_dir), env=env, check=True)
            
        if data_path.exists():
            print("Success: Datasets initialized.")
        else:
            print("Warning: Initialization scripts failed to create files. Please verify source data.")

def reset_database():
    """Delete the existing SQLite database to force re-initialization."""
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/database/users.db")
    if db_url.startswith("sqlite:///"):
        db_path_str = db_url.replace("sqlite:///", "")
        db_path = backend_dir / db_path_str
        if db_path.exists():
            print(f"[*] Resetting database: {db_path}...")
            try:
                os.remove(db_path)
                print("Database deleted successfully.")
            except Exception as e:
                print(f"Error deleting database: {e}")

def start_backend():
    """Start the FastAPI backend server."""
    print("Starting MURENA Backend...")
    try:
        subprocess.Popen([
            sys.executable, "-m", "uvicorn", "app.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload"
        ], cwd=str(backend_dir))
    except Exception as e:
        print(f"Failed to start backend: {e}")
        sys.exit(1)

def start_frontend():
    """Start the React frontend dev server."""
    frontend_dir = root_dir / "frontend"
    if not frontend_dir.exists():
        print("Warning: frontend directory not found. Skipping frontend start.")
        return

    # Check if npm exists in the path
    if not shutil.which("npm"):
        print("Warning: 'npm' command not found. Node.js is required for the frontend. Skipping frontend start.")
        return

    print("Starting MURENA Frontend...")
    try:
        # Check if node_modules exists
        if not (frontend_dir / "node_modules").exists():
            print("node_modules not found. Running npm install...")
            subprocess.run(["npm", "install"], cwd=str(frontend_dir), check=True)
        
        subprocess.Popen(["npm", "run", "dev"], cwd=str(frontend_dir))
    except Exception as e:
        print(f"Failed to start frontend: {e}")

def create_user():
    """Create a new user in the database."""
    print("=== MURENA User Creator ===")
    from app.database.connection import SessionLocal
    from app.repositories import UserRepository
    from app.core.security import get_password_hash
    
    username = input("Username: ").strip()
    email = input("Email: ").strip()
    password = getpass("Password: ")
    confirm = getpass("Confirm Password: ")
    
    if password != confirm:
        print("Error: Passwords do not match.")
        sys.exit(1)
        
    db = SessionLocal()
    try:
        repo = UserRepository(db)
        if not repo.verify_unique_username(username):
            print(f"Error: Username '{username}' already taken.")
            return
        hashed = get_password_hash(password)
        user = repo.create_user(username=username, password_hash=hashed, email=email)
        print(f"Success! User '{user.username}' created.")
    finally:
        db.close()

def delete_user():
    """Delete a user from the database."""
    print("=== MURENA User Deleter ===")
    from app.database.connection import SessionLocal
    from app.repositories import UserRepository
    
    username = input("Username to delete: ").strip()
    confirm = input(f"Are you sure you want to delete '{username}'? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("Operation cancelled.")
        return
        
    db = SessionLocal()
    try:
        repo = UserRepository(db)
        user = repo.get_user_by_username(username)
        if not user:
            print(f"Error: User '{username}' not found.")
            return
        repo.delete_user(user.id)
        print(f"Success! User '{username}' deleted.")
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Launch the MURENA Application")
    parser.add_argument("--skip-init", action="store_true", help="Skip data initialization check")
    parser.add_argument("--backend-only", action="store_true", help="Start only the backend")
    parser.add_argument("--create-user", action="store_true", help="Create a new user instead of starting app")
    parser.add_argument("--delete-user", action="store_true", help="Delete a user instead of starting app")
    args = parser.parse_args()

    check_prerequisites()
    
    if args.create_user:
        create_user()
        return
        
    if args.delete_user:
        delete_user()
        return

    print("=== MURENA Application Launcher ===")
    
    # Always reset database as requested
    reset_database()
    
    if not args.skip_init:
        init_data()

    start_backend()
    
    if not args.backend_only:
        time.sleep(2)  # Give backend a moment to start
        start_frontend()

    print("\nApplication is starting up.")
    print("- Backend: http://localhost:8000")
    print("- API Docs: http://localhost:8000/docs")
    if not args.backend_only:
        print("- Frontend: Check terminal for port (usually http://localhost:5173)")
    print("\nPress Ctrl+C to stop all services.")
    
    try:
        # Keep the main process alive until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down MURENA...")

if __name__ == "__main__":
    main()
