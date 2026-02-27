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

async def process_query(idx: int, query: str, config_dir: Path, semaphore: asyncio.Semaphore, disabled_agents: List[str] = None):
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

            # 2. Extract Agent Trace & Logic
            agent_trace = result.get("agent_trace", [])
            ranking_data = {}
            for t in agent_trace:
                if t.get("agent_name") == "ranking-agent":
                    out_raw = t.get("output")
                    if isinstance(out_raw, str):
                        ranking_data = safe_extract_json(out_raw) or {}
                    else:
                        ranking_data = out_raw
                    break

            # 3. Create individual JSON for summary
            summary_json = {
                "query": query,
                "disabled_agents": disabled_agents or [],
                "results_count": result.get("results_count", 0),
                "relaxation_applied": result.get("relaxation_applied", False),
                "execution_time_ms": duration_ms,
                "ranking_logic": {
                    "original_weights": ranking_data.get("weights", {}),
                    "reasoning": ranking_data.get("reasoning", "")
                },
                "final_sql": result.get("filters_applied", {}).get("final_sql", ""),
                "ranking": ranking
            }
            
            summary_file = config_dir / f"query_{idx+1:03d}.json"
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(summary_json, f, indent=4, ensure_ascii=False)
            
            print(f"[SUCCESS] Query {idx+1} completed in {duration_ms}ms")
                
        except Exception as e:
            print(f"[ERROR] Query {idx+1} failed: {e}")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, help="LLM model flavor (e.g. gpt-4o, open-weights)")
    parser.add_argument("--csv", type=str, default="ablation_composed_queries.csv", help="CSV file to process")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of parallel queries")
    args = parser.parse_args()

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
    queries_to_run = df_queries["query"].tolist()

    print(f"[INFO] Running Ablation on {len(queries_to_run)} queries across {len(agents_to_ablate)} configurations")
    await preload_data()
    
    semaphore = asyncio.Semaphore(args.concurrency)
    
    for ablate_agent in agents_to_ablate:
        config_id = f"no_{ablate_agent}" if ablate_agent else "all_enabled"
        config_dir = output_root / config_id
        config_dir.mkdir(exist_ok=True)
        
        disabled_list = [ablate_agent] if ablate_agent else []
        
        print(f"\n[CONFIG] Starting config: {config_id.upper()}")
        
        tasks = [
            process_query(idx, query, config_dir, semaphore, disabled_agents=disabled_list)
            for idx, query in enumerate(queries_to_run)
        ]
        
        await asyncio.gather(*tasks)
        print(f"[SUCCESS] Completed config: {config_id}")

    print(f"\n[SUCCESS] Full Ablation Study finished. Results in {output_root}")

if __name__ == "__main__":
    asyncio.run(main())
