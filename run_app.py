import os
import sys
import subprocess
import argparse
import time
import shutil
import socket
from pathlib import Path
from getpass import getpass
from dotenv import load_dotenv

def make_link(url, text=None):
    """Create an OSC 8 terminal link with blue color and underline."""
    if text is None:
        text = url
    # Blue: \033[34m, Underline: \033[4m, Reset: \033[0m
    return f"\033]8;;{url}\033\\\033[34m\033[4m{text}\033[0m\033]8;;\033\\"

# Add backend to sys.path
root_dir = Path(__file__).resolve().parent
backend_dir = root_dir / "backend"
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

def init_data(use_real_pipeline: bool = False):
    """Initialize datasets if they are missing.

    Local demos should not depend on the raw APE/OSM sources used by the
    research pipeline, because those sources are intentionally not versioned.
    """
    metadata_dir = backend_dir / "data" / "metadata"
    data_path = metadata_dir / "estates.parquet"
    
    if not data_path.exists():
        print("Dataset not found or incomplete. Starting initialization...")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(backend_dir)

        create_demo_dataset = metadata_dir / "create_demo_dataset.py"
        if not use_real_pipeline and create_demo_dataset.exists():
            print("Creating local synthetic demo dataset...")
            subprocess.run(
                [sys.executable, str(create_demo_dataset)],
                cwd=str(root_dir),
                env=env,
                check=True,
            )
            if data_path.exists():
                return
        
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
        
        if not poi_path.exists() and create_pois.exists():
            subprocess.run([sys.executable, str(create_pois)], cwd=str(backend_dir), env=env, check=True, stdout=subprocess.DEVNULL)

        if not data_path.exists() and create_estate_dataset.exists():
            subprocess.run([sys.executable, str(create_estate_dataset)], cwd=str(backend_dir), env=env, check=True)
            
        if data_path.exists():
            pass
        else:
            print("Warning: Initialization scripts failed to create files. Please verify source data.")

def reset_database():
    """Delete the existing SQLite database to force re-initialization."""
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/database/users.db")
    if db_url.startswith("sqlite:///"):
        db_path_str = db_url.replace("sqlite:///", "")
        db_path = backend_dir / db_path_str
        if db_path.exists():
            try:
                os.remove(db_path)
            except Exception as e:
                print(f"Error deleting database: {e}")

def find_available_port(preferred_port: str, max_attempts: int = 20) -> str:
    """Return the preferred port if free, otherwise the next free port."""
    try:
        start = int(preferred_port)
    except (TypeError, ValueError):
        start = 5173

    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return str(port)

    raise RuntimeError(f"No available port found from {start} to {start + max_attempts - 1}")

def start_backend():
    """Start the FastAPI backend server."""
    try:
        port = os.getenv("PORT", "8000")
        backend_url = f"http://localhost:{port}"
        print(f"MURENA Backend: {make_link(backend_url)}")
        
        uvicorn_cmd = [
            sys.executable, "-m", "uvicorn", "app.main:app", 
            "--host", "0.0.0.0", 
            "--reload",
            "--log-level", "error"
        ]
        uvicorn_cmd.extend(["--port", port])
            
        subprocess.Popen(uvicorn_cmd, cwd=str(backend_dir), stdout=subprocess.DEVNULL)
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

    frontend_port = find_available_port(os.getenv("FRONTEND_PORT", "5173"))
    frontend_url = f"http://localhost:{frontend_port}"
    print(f"MURENA Frontend: {make_link(frontend_url)}")
    try:
        # Check if npm install is needed
        package_json = frontend_dir / "package.json"
        package_lock = frontend_dir / "package-lock.json"
        node_modules = frontend_dir / "node_modules"
        
        install_needed = False
        vite_bin = frontend_dir / "node_modules" / ".bin" / "vite"
        
        if not node_modules.exists() or not vite_bin.exists():
            install_needed = True
        elif package_json.exists():
            # Check if package.json or package-lock.json is newer than node_modules
            mtime_node_modules = node_modules.stat().st_mtime
            if package_json.stat().st_mtime > mtime_node_modules:
                install_needed = True
            elif package_lock.exists() and package_lock.stat().st_mtime > mtime_node_modules:
                install_needed = True

        if install_needed:
            subprocess.run(["npm", "install"], cwd=str(frontend_dir), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Update node_modules timestamp to avoid repeated installs if they were already up to date
            # but NPM didn't touch the directory timestamp
            try:
                node_modules.touch()
            except Exception:
                pass
        
        frontend_env = os.environ.copy()
        frontend_env["FRONTEND_PORT"] = frontend_port
        frontend_env["VITE_BACKEND_PORT"] = os.getenv("PORT", "8000")
        subprocess.Popen(
            [
                "npm",
                "run",
                "dev",
                "--",
                "--host",
                "0.0.0.0",
                "--port",
                frontend_port,
                "--strictPort",
            ],
            cwd=str(frontend_dir),
            env=frontend_env,
            stdout=subprocess.DEVNULL,
        )
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
    parser.add_argument(
        "--real-data-init",
        action="store_true",
        help="Use the real APE/OSM data pipeline if estates.parquet is missing",
    )
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


    
    # Always reset database as requested
    reset_database()
    
    if not args.skip_init:
        init_data(use_real_pipeline=args.real_data_init)

    start_backend()
    
    if not args.backend_only:
        time.sleep(2)  # Give backend a moment to start
        start_frontend()


    
    try:
        # Keep the main process alive until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down MURENA...")

if __name__ == "__main__":
    main()
