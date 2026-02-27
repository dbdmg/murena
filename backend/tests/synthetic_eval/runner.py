#!/usr/bin/env python3
"""
Test Completo Sistema Synthetic Evaluation - ALL-IN-ONE STANDALONE (Modularized)

Refactored runner for synthetic evaluation.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
# backend/tests/synthetic_eval/runner.py -> backend
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

load_dotenv()

from tests.synthetic_eval.config import USE_CASE_CONFIGS
from tests.synthetic_eval.orchestrator import SyntheticEvaluationTest


def run_all_use_cases(num_immobili: int, num_poi: int, num_runs: int) -> bool:
    """Esegue test su tutti gli use case e genera report aggregato."""
    
    print("\n" + "="*80)
    print("TEST MULTI-USE-CASE - TUTTI GLI USE CASE".center(80))
    print("="*80)
    print(f"\nConfigurazione:")
    print(f"  - Use Cases: {len(USE_CASE_CONFIGS)}")
    print(f"  - Immobili per use case: {num_immobili}")
    print(f"  - POI per categoria: {num_poi}")
    print(f"  - Consistency runs: {num_runs}")
    print(f"\n" + "="*80)
    
    for i, use_case in enumerate(USE_CASE_CONFIGS.keys(), 1):
        print(f"\n\n" + "#"*80)
        print(f"# USE CASE {i}/{len(USE_CASE_CONFIGS)}: {use_case.upper()}")
        print("#"*80)
        
        tester = SyntheticEvaluationTest(
            use_case=use_case,
            num_immobili=num_immobili,
            num_poi=num_poi,
            num_runs=num_runs
        )
        
        success = tester.run_full_test()
        
        if success:
            print(f" Use Case {use_case} completato con successo")
        else:
            print(f" Use Case {use_case} FALLITO")
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic Evaluation System")
    parser.add_argument("--use-case", type=str, help="Specific use case to test (default: all)")
    parser.add_argument("--num-immobili", type=int, default=50, help="Number of properties to generate")
    parser.add_argument("--num-poi", type=int, default=5, help="Number of POIs per category")
    parser.add_argument("--num-runs", type=int, default=3, help="Number of consistency runs")
    parser.add_argument("--ablation", action="store_true", help="Run ablation study")
    
    args = parser.parse_args()
    
    # Defaults handled here for single use case runs
    if args.use_case:
        if args.use_case not in USE_CASE_CONFIGS:
            print(f"Error: Use case '{args.use_case}' not found. Available: {list(USE_CASE_CONFIGS.keys())}")
            sys.exit(1)
            
        tester = SyntheticEvaluationTest(
            use_case=args.use_case,
            num_immobili=args.num_immobili,
            num_poi=args.num_poi,
            num_runs=args.num_runs,
            ablation_mode=args.ablation
        )
        
        if args.ablation:
            tester.run_full_ablation()
        else:
            tester.run_full_test()
            
    else:
        # Run all use cases
        if args.ablation:
            print("Running ablation on ALL use cases...")
            for uc in USE_CASE_CONFIGS:
                tester = SyntheticEvaluationTest(
                    use_case=uc,
                    num_immobili=args.num_immobili,
                    num_poi=args.num_poi,
                    num_runs=args.num_runs,
                    ablation_mode=True
                )
                tester.run_full_ablation()
        else:
            run_all_use_cases(args.num_immobili, args.num_poi, args.num_runs)
