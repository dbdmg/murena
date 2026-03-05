"""
Test script for a specific real estate query (Refined Debug Mode).
Following the pattern of generate_synthetic_test_dirs.py for robust execution and trace extraction.
"""

import os
import sys
import asyncio
import json
import logging
import argparse
import time
from pathlib import Path
from datetime import datetime

# 1. Setup paths and environment
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# 2. Suppress standard logging for cleaner output
logging.basicConfig(level=logging.ERROR)
logging.getLogger().setLevel(logging.ERROR)

from dotenv import load_dotenv
load_dotenv(BACKEND_ROOT / ".env")

from app.core.config import settings

# Patch settings with absolute paths to allow running from any CWD
for attr in ["DATASET_FULL", "APE_DETAILED_DATA_PATH", "STATIC_DIR", "DATA_DIR", "APE_DIR", "META_DIR", "AGENT_LOGS_DIR"]:
    val = getattr(settings, attr, None)
    if val and isinstance(val, str) and not os.path.isabs(val):
        setattr(settings, attr, str(BACKEND_ROOT / val))

from app.services.analysis_service import analysis_service
from app.services.real_estate_service import RealEstateService
from app.data.loaders import load_and_merge_data
from app.utils.json_parser import safe_extract_json

# 3. Suppress loguru logging (used by the backend)
try:
    from loguru import logger
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
except ImportError:
    pass

async def preload_data():
    """Preload the dataset into memory to ensure consistent behavior."""
    dataset_path = Path(settings.DATASET_FULL)
    if dataset_path.exists():
        print(f"[LOAD] Preloading dataset from {dataset_path.name}...")
        df = await asyncio.to_thread(load_and_merge_data, str(dataset_path))
        
        # Populate global caches
        RealEstateService._dataset_cache["full"] = df
        analysis_service._base_dataset_cache["full"] = df
        
        if "id" in df.columns:
            df_indexed = df.copy()
            df_indexed["id_str"] = df_indexed["id"].astype(str)
            df_indexed = df_indexed.drop_duplicates(subset=["id_str"])
            df_indexed.set_index("id_str", inplace=True)
            RealEstateService._dataset_indexed_cache["full"] = df_indexed
        return True
    return False

async def test_specific_query(model_choice: str, query: str) -> None:
    """
    Esegue una query immobiliare specifica con estrazione avanzata dei risultati.
    """
    # Configura il modello
    print(f"[CONFIG] Modello: {model_choice}")
    settings.set_llm_model(model_choice)
    
    # Abilita log e export per debug
    settings.ENABLE_RUN_JSON_EXPORT = True
    settings.DEBUG = True
    os.environ["RUN_REAL_LLM_TESTS"] = "1"
    
    # Assicura il precaricamento dei dati
    await preload_data()
    
    run_id = f"test_debug_{model_choice}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"[LANCIO] Query: '{query}'")
    start_t = time.time()
    
    try:
        result = await analysis_service.run_analysis(
            run_id=run_id,
            query=query,
            dataset_key="full",
            map_limit=1000,
            llm_limit=25,
            analysis_mode="agent"
        )
        
        duration_ms = round((time.time() - start_t) * 1000, 2)
        print(f"[FINE]   Esecuzione completata in {duration_ms}ms")
        
        # --- Estrazione Tracce e Logiche (Pattern Synthetic Test) ---
        agent_trace = result.get("agent_trace", [])
        gemini_responses = result.get("gemini_responses", {})
        
        # Identifica agenti attivi che hanno prodotto risultati
        agents_with_requirements = {}
        ranking_data = None
        
        for entry in agent_trace:
            name = entry.get("agent_name", "").replace("-agent", "").replace("-", "_").lower()
            out_raw = entry.get("output")
            
            if isinstance(out_raw, str):
                out = safe_extract_json(out_raw) or out_raw
            else:
                out = out_raw
            
            if not out or not isinstance(out, dict):
                continue
                
            if name == "ranking":
                ranking_data = out
                continue

            has_reqs = False
            req_data = None
            
            if name == "location":
                if out.get("places"):
                    has_reqs = True
                    req_data = out["places"]
            elif name == "property_technical":
                typologies = out.get("typologies", [])
                requisiti = out.get("requisiti", [])
                if typologies or requisiti:
                    has_reqs = True
                    req_data = {"typologies": typologies, "requisiti": requisiti}
            elif name in ["ape", "poi", "normative"]:
                if out.get("found") or out.get("requisiti"):
                    has_reqs = True
                    req_data = out.get("requisiti", [])
                    
            if has_reqs:
                agents_with_requirements[name] = req_data

        # Calcolo logica di ranking (redistribuzione pesi)
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
                
                # Fix precisione
                diff = round(1.0 - sum(effective_weights.values()), 2)
                if diff != 0 and active_and_found:
                    max_agent = max(active_and_found, key=lambda a: effective_weights[a])
                    effective_weights[max_agent] = round(effective_weights[max_agent] + diff, 2)
            
            ranking_logic = {
                "original_weights": initial_weights,
                "effective_weights": effective_weights,
                "reasoning": ranking_data.get("reasoning", "")
            }

        # Estrazione Top 10 Ranking
        buildings = result.get("buildings", [])
        final_ranking = []
        for b in buildings[:10]:
            final_ranking.append({
                "id": str(b.id),
                "score": float(round(b.score, 1))
            })

        # Struttura l'output finale
        output_json = {
            "query": query,
            "model": model_choice,
            "run_id": run_id,
            "results_count": result.get("results_count", 0),
            "relaxation_applied": result.get("relaxation_applied", False),
            "execution_time_ms": duration_ms,
            "ranking_logic": ranking_logic,
            "final_sql": result.get("filters_applied", {}).get("final_sql", ""),
            "ranking": final_ranking,
            "agents_requirements": agents_with_requirements,
            "raw_responses": gemini_responses,
            "full_trace": agent_trace
        }
        
        # Salva l'output
        output_dir = BACKEND_ROOT / "scripts" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{run_id}.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_json, f, indent=4, ensure_ascii=False)
            
        print(f"[SUCCESS] Risultati salvati in: {output_file}")
            
    except Exception as e:
        print(f"[ERROR] Esecuzione fallita: {e}")
        error_json = {
            "status": "error",
            "error_message": str(e),
            "query": query,
            "model": model_choice
        }
        
        output_dir = BACKEND_ROOT / "scripts" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{run_id}_error.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(error_json, f, indent=4, ensure_ascii=False)
        print(f"[ERROR] Errore salvato in: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test script for real estate queries (Synthetic-style Debug).")
    parser.add_argument(
        "--model", 
        type=str, 
        choices=["gpt-5-nano", "gpt-oss-120b"], 
        default="gpt-5-nano",
        help="Model to use"
    )
    parser.add_argument(
        "--query", 
        type=str, 
        default="Cerca un abitazione con superficie tra 50 e 80 mq in classe C o più efficiente, finalizzato a centro per anziani",
        help="The query to test"
    )
    
    args = parser.parse_args()
    
    asyncio.run(test_specific_query(args.model, args.query))
