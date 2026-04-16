import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add backend to sys.path
root_dir = Path(__file__).resolve().parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Change CWD to backend to match relative paths in .env
os.chdir(backend_dir)

# Initialize environment variables
from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

from app.services.analysis_service import analysis_service

async def test_pipeline():
    print("=== Testing Agentic Pipeline ===")
    
    run_id = str(uuid.uuid4())
    query = "Cerco uffici commerciali a Torino con buona efficienza energetica (classe A o B)."
    
    print(f"Query: {query}")
    print(f"Run ID: {run_id}")
    print("-" * 30)

    # Callback to show progress in console
    def progress_callback(progress_tuple):
        percent, steps = progress_tuple
        current_step = next((s["label"] for s in steps if s["state"] == "current"), "Processing")
        print(f"[{percent:3.0f}%] {current_step}...")

    try:
        # Run the analysis
        print("Starting analysis...")
        results = await analysis_service.run_analysis(
            run_id=run_id,
            query=query,
            dataset_key="full",
            progress_callback=progress_callback
        )
        
        print("-" * 30)
        print(f"Status: {results.get('status')}")
        print(f"Buildings found: {len(results.get('buildings', []))}")
        
        if results.get("location"):
            print(f"Detected locations: {results['location']}")
            
        if results.get("filters_applied"):
            print(f"SQL Generated: {results['filters_applied'].get('final_sql')}")
            
        if results.get("broker_summary"):
            print("\n--- EXECUTIVE SUMMARY ---")
            print(results["broker_summary"])
            print("-" * 30)
            
        print("\nSuccess! Agentic pipeline test completed.")
        
    except Exception as e:
        print(f"\nPipeline failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pipeline())
