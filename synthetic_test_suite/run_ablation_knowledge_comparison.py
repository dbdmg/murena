
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

async def run_ablation_knowledge():
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

    output_dir = suite_dir / "ablation_knowledge_results" / args.model
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Progress tracking: copy CSV to output dir if it doesn't exist
    queries_csv = output_dir / args.csv
    if not queries_csv.exists():
        shutil.copy(input_csv, queries_csv)
        print(f"[INFO] Copied {args.csv} to {output_dir}")
        
    # Read/Initialize status in the copied CSV
    async with csv_lock:
        df_queries = pd.read_csv(queries_csv)
        if "status_knowledge" not in df_queries.columns:
            df_queries["status_knowledge"] = 0
            df_queries.to_csv(queries_csv, index=False)
    
    await preload_data()
    
    semaphore = asyncio.Semaphore(args.concurrency)
    
    async def process_query(idx, query):
        async with semaphore:
            # Check if already processed
            async with csv_lock:
                df = pd.read_csv(queries_csv)
                if df.iloc[idx].get("status_knowledge", 0) != 0:
                    print(f"[SKIP] Query {idx+1} already processed or in progress.")
                    return
                # Mark as in progress (1)
                df.at[idx, "status_knowledge"] = 1
                df.to_csv(queries_csv, index=False)

            print(f"[START] Query {idx+1}/{len(df_queries)}: {query[:50]}...")
            try:
                # 1. Run WITH Knowledge
                print(f"[PROCES] Query {idx+1}: (1/2) Running WITH knowledge...")
                start_t_with = time.time()
                run_id_with = f"knowledge_with_{args.model}_{idx+1}_{int(time.time())}"
                
                result_with = await analysis_service.run_analysis(
                    run_id=run_id_with,
                    query=query,
                    dataset_key="full",
                    map_limit=15000,
                    llm_limit=25,
                    analysis_mode="agent",
                    use_data_knowledge=True
                )
                duration_with = round((time.time() - start_t_with) * 1000, 2)
                
                # 2. Run WITHOUT Knowledge
                print(f"[PROCES] Query {idx+1}: (2/2) Running WITHOUT knowledge...")
                start_t_without = time.time()
                run_id_without = f"knowledge_without_{args.model}_{idx+1}_{int(time.time())}"
                
                result_without = await analysis_service.run_analysis(
                    run_id=run_id_without,
                    query=query,
                    dataset_key="full",
                    map_limit=15000,
                    llm_limit=25,
                    analysis_mode="agent",
                    use_data_knowledge=False
                )
                duration_without = round((time.time() - start_t_without) * 1000, 2)
                
                # Extract results
                def get_top_10(res):
                    buildings = []
                    for b in res.get("buildings", []):
                        buildings.append({
                            "id": str(b.id),
                            "score": float(b.score if b.score is not None else 0.0)
                        })
                    return sorted(buildings, key=lambda x: x["score"], reverse=True)[:10]

                with_top_10 = get_top_10(result_with)
                without_top_10 = get_top_10(result_without)
                
                output_json = {
                    "query": query,
                    "with_knowledge": {
                        "execution_time_ms": duration_with,
                        "relaxation_applied": result_with.get("relaxation_applied", False),
                        "final_sql": result_with.get("filters_applied", {}).get("final_sql", ""),
                        "top_10_buildings": with_top_10
                    },
                    "without_knowledge": {
                        "execution_time_ms": duration_without,
                        "relaxation_applied": result_without.get("relaxation_applied", False),
                        "final_sql": result_without.get("filters_applied", {}).get("final_sql", ""),
                        "top_10_buildings": without_top_10
                    }
                }
                
                output_file = output_dir / f"query_{idx+1:03d}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(output_json, f, indent=4, ensure_ascii=False)
                
                # Mark as success (2)
                async with csv_lock:
                    df = pd.read_csv(queries_csv)
                    df.at[idx, "status_knowledge"] = 2
                    df.to_csv(queries_csv, index=False)
                
                print(f"[SUCCESS] Query {idx+1} completed.")
                
            except Exception as e:
                print(f"[ERROR] Query {idx+1} failed: {e}")
                # Mark as error (3)
                async with csv_lock:
                    df = pd.read_csv(queries_csv)
                    df.at[idx, "status_knowledge"] = 3
                    df.to_csv(queries_csv, index=False)
                import traceback
                traceback.print_exc()

    tasks = [process_query(i, row["query"]) for i, row in df_queries.iterrows()]
    await asyncio.gather(*tasks)
    print(f"\n[DONE] All results saved in {output_dir}")

if __name__ == "__main__":
    asyncio.run(run_ablation_knowledge())
