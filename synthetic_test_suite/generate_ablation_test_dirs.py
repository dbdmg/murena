import asyncio
import json
import os
import pandas as pd
import numpy as np
import sys
import logging
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

# 1. Suppress standard logging
logging.basicConfig(level=logging.ERROR)
logging.getLogger().setLevel(logging.ERROR)

# Add backend folder to sys.path so 'app' is found correctly
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
from app.services.real_estate_service import RealEstateService
from app.data.loaders import load_and_merge_data

# 2. Suppress loguru logging (used by the backend)
try:
    from loguru import logger
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
except ImportError:
    pass

def safe_extract_json(text: str) -> Optional[Dict]:
    """Extract first JSON object from a string."""
    if not text or not isinstance(text, str):
        return None
    try:
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1:
            return json.loads(text[start_idx : end_idx + 1])
    except:
        pass
    return None

async def preload_data():
    """Preload the dataset into memory."""
    dataset_path = Path(settings.DATASET_FULL)
    if dataset_path.exists():
        df = load_and_merge_data(str(dataset_path))
        
        # Populate caches to avoid disk loading
        RealEstateService._dataset_cache["full"] = df
        analysis_service._base_dataset_cache["full"] = df
        
        if "id" in df.columns:
            df_indexed = df.copy()
            df_indexed["id_str"] = df_indexed["id"].astype(str)
            df_indexed = df_indexed.drop_duplicates(subset=["id_str"])
            df_indexed.set_index("id_str", inplace=True)
            RealEstateService._dataset_indexed_cache["full"] = df_indexed
    return True

async def run_single_test(prompt: str, disabled_agents: List[str] = None):
    """Run the analysis and collect rankings using graph_orchestrator."""
    disabled_str = f" [Disabled: {', '.join(disabled_agents)}]" if disabled_agents else " [All Enabled]"
    print(f"[LANCIO]{disabled_str} Prompt: {prompt[:80]}...")
    try:
        run_id = f"ablation_{datetime.now().strftime('%H%M%S')}"
        result = await analysis_service.run_analysis(
            run_id=run_id,
            query=prompt,
            dataset_key="full",
            map_limit=15000,
            llm_limit=25,
            analysis_mode="agent",
            disabled_agents=disabled_agents
        )
        return result
    except Exception as e:
        print(f"[ERROR] Run failed: {e}")
        return {}

async def process_query(idx: int, query: str, config_dir: Path, semaphore: asyncio.Semaphore, disabled_agents: List[str] = None, csv_lock: asyncio.Lock = None, df_queries: pd.DataFrame = None, queries_csv: Path = None, status_col: str = None):
    """Process a single query, save results."""
    async with semaphore:
        try:
            start_t = time.time()
            result = await run_single_test(query, disabled_agents=disabled_agents)
            duration_ms = round((time.time() - start_t) * 1000, 2)
            
            # 1. Prepare Ranking Output
            buildings = result.get("buildings", [])
            ranking = []
            for b in buildings[:10]:
                bid = b.get("id") if isinstance(b, dict) else getattr(b, "id", None)
                score = b.get("score", 0.0) if isinstance(b, dict) else getattr(b, "score", 0.0)
                if bid:
                    ranking.append({
                        "id": str(bid),
                        "score": float(round(score, 1))
                    })

            # 2. Extract Agent Trace & Logic e calcola i pesi effettivi
            agent_trace = result.get("agent_trace", [])
            ranking_data = {}
            agents_with_requirements = {}
            
            for t in agent_trace:
                name = t.get("agent_name", "").replace("-agent", "").replace("-", "_").lower()
                out_raw = t.get("output")
                
                # Estrazione sicura sia per stringhe JSON che per dict
                out = safe_extract_json(out_raw) if isinstance(out_raw, str) else out_raw
                if not out or not isinstance(out, dict):
                    continue

                if name == "ranking":
                    ranking_data = out
                    continue

                has_reqs = False
                if name == "location":
                    if out.get("places") and len(out["places"]) > 0:
                        has_reqs = True
                elif name == "property_technical":
                    if out.get("typologies", []) or out.get("requisiti", []):
                        has_reqs = True
                elif name in ["ape", "poi", "normative"]:
                    if out.get("found") or (out.get("requisiti") and len(out["requisiti"]) > 0):
                        has_reqs = True
                        
                if has_reqs:
                    agents_with_requirements[name] = True

            # Calcolo della ridistribuzione dei pesi (effective_weights)
            ranking_logic = {}
            if ranking_data:
                initial_weights = ranking_data.get("weights", {})
                found_agent_keys = set(agents_with_requirements.keys())
                
                active_and_found = [a for a, w in initial_weights.items() if w > 0 and a in found_agent_keys]
                remaining_weight_sum = sum(initial_weights.get(a, 0) for a in active_and_found)
                
                effective_weights = {}
                if remaining_weight_sum > 0:
                    for a in initial_weights.keys():
                        if a in active_and_found:
                            effective_weights[a] = round(initial_weights[a] / remaining_weight_sum, 2)
                        else:
                            effective_weights[a] = 0.0
                    
                    diff = round(1.0 - sum(effective_weights.values()), 2)
                    if diff != 0 and active_and_found:
                        max_agent = max(active_and_found, key=lambda a: effective_weights[a])
                        effective_weights[max_agent] = round(effective_weights[max_agent] + diff, 2)
                else:
                    effective_weights = {a: 0.0 for a in initial_weights.keys()}

                ranking_logic = {
                    "original_weights": initial_weights,
                    "effective_weights": effective_weights,
                    "reasoning": ranking_data.get("reasoning", "")
                }
            else:
                ranking_logic = {
                    "original_weights": {},
                    "effective_weights": {},
                    "reasoning": ""
                }

            # 3. Create individual JSON for summary
            summary_json = {
                "query": query,
                "disabled_agents": disabled_agents or [],
                "results_count": result.get("results_count", 0),
                "relaxation_applied": result.get("relaxation_applied", False),
                "execution_time_ms": duration_ms,
                "ranking_logic": ranking_logic,
                "final_sql": result.get("filters_applied", {}).get("final_sql", ""),
                "ranking": ranking
            }
            
            summary_file = config_dir / f"query_{idx+1:03d}.json"
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(summary_json, f, indent=4, ensure_ascii=False)
            
            if csv_lock and df_queries is not None and queries_csv and status_col:
                async with csv_lock:
                    df_queries.at[idx, status_col] = 1
                    df_queries.to_csv(queries_csv, index=False)
            
            print(f"[SUCCESS] Query {idx+1} completed in {duration_ms}ms")
                
        except Exception as e:
            print(f"[ERROR] Query {idx+1} failed: {e}")
            if csv_lock and df_queries is not None and queries_csv and status_col:
                async with csv_lock:
                    df_queries.at[idx, status_col] = 2
                    df_queries.to_csv(queries_csv, index=False)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, choices=["open-weights", "gpt-5-nano"], help="LLM model flavor")
    parser.add_argument("--csv", type=str, default="ablation_composed_queries.csv", help="CSV file to process")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of parallel queries")
    args, _ = parser.parse_known_args()

    if args.model:
        settings.set_llm_model(args.model)
        print(f"[CONFIG] Using model flavor: {args.model}")

    suite_dir = Path(__file__).parent
    queries_csv = suite_dir / args.csv
    
    if not queries_csv.exists():
        print(f"[ERROR] CSV not found: {queries_csv}")
        return

    output_root = suite_dir / "ablation_results"
    output_root.mkdir(exist_ok=True)
    
    # Define Agents to Ablate
    # We test each parallel agent disabled
    agents_to_ablate = [
        "poi",
        "normative",
        "location",
        "ape",
        "property_technical"
    ]

    df_queries = pd.read_csv(queries_csv)

    print(f"[INFO] Running Ablation on {len(df_queries)} queries across {len(agents_to_ablate)} configurations")
    await preload_data()
    
    semaphore = asyncio.Semaphore(args.concurrency)
    csv_lock = asyncio.Lock()
    
    for ablate_agent in agents_to_ablate:
        config_id = f"no_{ablate_agent}" if ablate_agent else "all_enabled"
        status_col = f"status_{config_id}"
        
        # Check and initialize status column if lacking
        if status_col not in df_queries.columns:
            df_queries[status_col] = 0
            df_queries.to_csv(queries_csv, index=False)
            
        pending_mask = df_queries[status_col] == 0
        pending_indices = df_queries[pending_mask].index.tolist()
        
        if not pending_indices:
            print(f"\n[CONFIG] Skipping {config_id.upper()} (all queries completed/error)")
            continue

        config_dir = output_root / config_id
        config_dir.mkdir(exist_ok=True)
        
        disabled_list = [ablate_agent] if ablate_agent else []
        
        print(f"\n[CONFIG] Starting config: {config_id.upper()} ({len(pending_indices)} pending)")
        
        tasks = [
            process_query(idx, df_queries.at[idx, "query"], config_dir, semaphore, disabled_agents=disabled_list, csv_lock=csv_lock, df_queries=df_queries, queries_csv=queries_csv, status_col=status_col)
            for idx in pending_indices
        ]
        
        await asyncio.gather(*tasks)
        print(f"[SUCCESS] Completed config: {config_id}")

    print(f"\n[SUCCESS] Full Ablation Study finished. Results in {output_root}")

if __name__ == "__main__":
    asyncio.run(main())
