
import asyncio
import json
import os
import pandas as pd
import numpy as np
import sys
import time
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add backend folder to sys.path
base_dir = Path(__file__).resolve().parent.parent
backend_dir = base_dir / "backend"
sys.path.append(str(backend_dir))

from app.core.config import settings
# Patch settings with absolute paths to allow running from root
for attr in ["DATASET_FULL", "APE_DETAILED_DATA_PATH", "STATIC_DIR", "DATA_DIR", "APE_DIR", "META_DIR", "AGENT_LOGS_DIR"]:
    val = getattr(settings, attr, None)
    if val and isinstance(val, str) and not os.path.isabs(val):
        setattr(settings, attr, str(backend_dir / val))

from app.services.analysis_service import analysis_service
from app.utils.json_parser import safe_extract_json

# Global lock for CSV updates
csv_lock = asyncio.Lock()

async def preload_data():
    """Preload necessary data for the analysis service."""
    from app.services.real_estate_service import RealEstateService
    from app.data.loaders import load_and_merge_data
    
    dataset_path = Path(settings.DATASET_FULL)
    print(f"[INFO] Loading dataset from: {dataset_path}")
    if dataset_path.exists():
        df = load_and_merge_data(str(dataset_path))
        RealEstateService._dataset_cache["full"] = df
        analysis_service._base_dataset_cache["full"] = df
        
        if "id" in df.columns:
            df_indexed = df.copy()
            df_indexed["id_str"] = df_indexed["id"].astype(str)
            df_indexed = df_indexed.drop_duplicates(subset=["id_str"])
            df_indexed.set_index("id_str", inplace=True)
            RealEstateService._dataset_indexed_cache["full"] = df_indexed
    return True

def calculate_simple_average(agent_scores: Dict[str, Dict[str, float]], active_agents: List[str]) -> Dict[str, float]:
    """
    Calculate the simple average score for each building.
    
    Args:
        agent_scores: Mapping from agent name to {building_id: score}
        active_agents: List of agents that returned requirements/ran ranking
        
    Returns:
        Mapping from building_id to average score
    """
    if not active_agents:
        return {}
        
    all_building_ids = set()
    for scores in agent_scores.values():
        all_building_ids.update(scores.keys())
        
    avg_scores = {}
    for bid in all_building_ids:
        total_score = 0.0
        count = 0
        for agent in active_agents:
            if agent in agent_scores:
                total_score += agent_scores[agent].get(bid, 0.0)
                count += 1
        
        if count > 0:
            avg_scores[bid] = round(total_score / len(active_agents), 2)
        else:
            avg_scores[bid] = 0.0
            
    return avg_scores

async def run_ablation_scoring():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, choices=["gpt-oss-120b", "gpt-5-nano", "deepseek-r1-8b"], default="gpt-5-nano", help="LLM model flavor")
    parser.add_argument("--csv", type=str, default="ablation_composed_queries.csv", help="CSV file to process")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of parallel queries")
    args, _ = parser.parse_known_args()

    if args.model:
        settings.set_llm_model(args.model)
        print(f"[CONFIG] Using model flavor: {args.model}")

    suite_dir = Path(__file__).parent
    input_csv = suite_dir / args.csv
    
    if not input_csv.exists():
        print(f"[ERROR] Input CSV not found: {input_csv}")
        return

    output_dir = suite_dir / "ablation_scoring_results" / args.model
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Progress tracking: copy CSV to output dir if it doesn't exist
    queries_csv = output_dir / args.csv
    if not queries_csv.exists():
        shutil.copy(input_csv, queries_csv)
        print(f"[INFO] Copied {args.csv} to {output_dir}")
        
    # Read/Initialize status in the copied CSV
    async with csv_lock:
        df_queries = pd.read_csv(queries_csv)
        if "status_scoring" not in df_queries.columns:
            df_queries["status_scoring"] = 0
            df_queries.to_csv(queries_csv, index=False)
    
    await preload_data()
    
    semaphore = asyncio.Semaphore(args.concurrency)
    
    async def process_query(idx, query):
        async with semaphore:
            # Check if already processed
            async with csv_lock:
                df = pd.read_csv(queries_csv)
                if df.iloc[idx].get("status_scoring", 0) != 0:
                    print(f"[SKIP] Query {idx+1} already processed or in progress.")
                    return
                # Mark as in progress (1)
                df.at[idx, "status_scoring"] = 1
                df.to_csv(queries_csv, index=False)

            print(f"[START] Query {idx+1}/{len(df_queries)}: {query[:50]}...")
            try:
                start_t = time.time()
                run_id = f"ablation_{args.model}_{idx+1}_{int(time.time())}"
                
                result = await analysis_service.run_analysis(
                    run_id=run_id,
                    query=query,
                    dataset_key="full",
                    map_limit=15000,
                    llm_limit=25,
                    analysis_mode="agent"
                )
                
                duration_ms = round((time.time() - start_t) * 1000, 2)
                
                # Extract individual agent scores
                agent_scores = {}
                really_found_agents = []
                
                trace = result.get("agent_trace", [])
                for entry in trace:
                    agent_name = entry.get("agent_name", "").replace("-agent", "").replace("-", "_").lower()
                    mode = entry.get("agent_mode", "")
                    
                    if mode == "ranking" and agent_name != "ranking":
                        really_found_agents.append(agent_name)
                        scores = {}
                        output = entry.get("output", [])
                        if isinstance(output, list):
                            for item in output:
                                if isinstance(item, dict) and "id" in item:
                                    scores[str(item["id"])] = float(item.get("score", 0.0))
                        agent_scores[agent_name] = scores
                
                # Strategy A
                strategy_a_results = []
                for b in result.get("buildings", []):
                    strategy_a_results.append({
                        "id": str(b.id),
                        "score": float(b.score if b.score is not None else 0.0)
                    })
                strategy_a_top_10 = sorted(strategy_a_results, key=lambda x: x["score"], reverse=True)[:10]
                
                # Strategy B
                avg_scores = calculate_simple_average(agent_scores, really_found_agents)
                strategy_b_results = []
                for bid, score in avg_scores.items():
                    strategy_b_results.append({
                        "id": bid,
                        "score": score
                    })
                strategy_b_top_10 = sorted(strategy_b_results, key=lambda x: x["score"], reverse=True)[:10]
                
                output_json = {
                    "query": query,
                    "execution_time_ms": duration_ms,
                    "active_agents": really_found_agents,
                    "relaxation_applied": result.get("relaxation_applied", False),
                    "final_sql": result.get("filters_applied", {}).get("final_sql", ""),
                    "ranking_logic": result.get("context", {}).get("ranking_result", {}).get("weights", {}) if result.get("context") else {},
                    "strategy_a_ranking": strategy_a_top_10,
                    "strategy_b_simple_average": strategy_b_top_10
                }
                
                output_file = output_dir / f"query_{idx+1:03d}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(output_json, f, indent=4, ensure_ascii=False)
                
                # Mark as success (2)
                async with csv_lock:
                    df = pd.read_csv(queries_csv)
                    df.at[idx, "status_scoring"] = 2
                    df.to_csv(queries_csv, index=False)
                
                print(f"[SUCCESS] Query {idx+1} completed.")
                
            except Exception as e:
                print(f"[ERROR] Query {idx+1} failed: {e}")
                # Mark as error (3)
                async with csv_lock:
                    df = pd.read_csv(queries_csv)
                    df.at[idx, "status_scoring"] = 3
                    df.to_csv(queries_csv, index=False)
                import traceback
                traceback.print_exc()

    tasks = [process_query(i, row["query"]) for i, row in df_queries.iterrows()]
    await asyncio.gather(*tasks)
    print(f"\n[DONE] All results saved in {output_dir}")

if __name__ == "__main__":
    asyncio.run(run_ablation_scoring())
