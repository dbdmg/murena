import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

def check_prerequisites():
    """Check if basic requirements are met."""
    if not (backend_dir / ".env").exists():
        print("Error: .env file not found in backend directory.")
        print("Please create it from .env.example first.")
        sys.exit(1)
        
def init_data():
    """Import and run data initialization logic from run_app."""
    try:
        from run_app import init_data as start_init
        start_init()
    except ImportError:
        print("Warning: run_app.py not found for initialization.")

def run_experiment_script(script_name: str, args: list = None):
    """Run a specific experiment script."""
    script_path = backend_dir / "tests" / script_name
    if not script_path.exists():
        print(f"Error: Experiment script not found at {script_path}.")
        return False

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    print(f"Running experiment: {script_name}...")
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Experiment failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Launcher for MURENA Experiments and Evaluation")
    parser.add_argument("--type", choices=["baseline", "sampled", "all"], default="sampled", help="Experiment type")
    parser.add_argument("--limit", type=int, default=10, help="Number of samples to run")
    parser.add_argument("--export", action="store_true", help="Export results to CSV/JSON")
    args = parser.parse_args()

    print("=== MURENA Experiment Runner ===")
    check_prerequisites()
    init_data()

    if args.type == "baseline":
        run_experiment_script("test_suite.py", ["--model", "gpt-5.4"])
    elif args.type == "sampled":
        run_experiment_script("test_suite.py", ["--max-concurrent", "10"])
    elif args.type == "all":
        run_experiment_script("test_suite.py")

    print("\nExperiments completed. Results can be found in the results/ directory.")

if __name__ == "__main__":
    main()
