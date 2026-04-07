import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add parent directory to sys.path to import metrics and results_formatter
sys.path.append(str(Path(__file__).resolve().parent))
from metrics import analyze_activation, analyze_ranking_differentiation, analyze_ranking_consistency, analyze_performance, evaluate_with_judge
from results_formatter import format_table_1, format_table_2

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Configuration
RESULTS_ROOT = Path(os.environ.get("RESULTS_ROOT", "backend/tests/results"))
METADATA_DIR = Path(os.environ.get("EXPERIMENT_METADATA_DIR", "backend/experiments/data/metadata"))

def get_model_results(model: str) -> Dict[str, Any]:
    """Helper to load all metrics for a given model from existing result directories."""
    out_root = RESULTS_ROOT / "outputs" / "benchmarks" / model
    out_sens = RESULTS_ROOT / "outputs" / "sensitivity" / model
    
    if not out_root.exists():
        logging.warning(f"Result directory for {model} not found in {out_root}")
        return {}

    mapping_path = METADATA_DIR / "agent_ground_truth.json"
    
    return {
        "activation": analyze_activation(out_root / "full", mapping_path, model),
        "ranking_stats": {
            "differentiation": analyze_ranking_differentiation(out_root / "full"),
            "consistency": analyze_ranking_consistency(out_root / "consistency")
        },
        "performance": analyze_performance(out_root / "full"),
        "eval_quality": {} # This would be filled by judge analysis
    }

def main():
    parser = argparse.ArgumentParser(description="MURENA Paper Results Reproduction Script")
    parser.add_argument("--table", choices=["1", "2", "all"], default="all", help="Select table to reproduce")
    parser.add_argument("--format", choices=["latex", "text"], default="latex", help="Output format")
    args = parser.parse_args()

    models = ["gpt-oss-120b", "gemma3-27b", "qwen3-8b"]
    all_results = {}
    
    print("\n--- MURENA Paper Reproducibility CLI ---")
    print(f"Dataset: ~90,000 Italian EPC Certificates")
    print(f"Log directory: {RESULTS_ROOT}\n")

    for model in models:
        all_results[model] = get_model_results(model)

    if args.table in ["1", "all"]:
        print("--- Table 1: Routing, Ranking, Qualitative (Page 11) ---")
        latex_t1 = format_table_1(all_results)
        print(latex_t1)
        
    if args.table in ["2", "all"]:
        print("\n--- Table 2: Monolithic vs Multi-Agent (Page 13) ---")
        latex_t2 = format_table_2(all_results)
        print(latex_t2)

    print("\nIndividual JSON metrics can be found in the backend/experiments/report/ metadata folder.")

if __name__ == "__main__":
    main()
