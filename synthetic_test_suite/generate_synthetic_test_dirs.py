
import asyncio
import json
import os
import pandas as pd
import numpy as np
import sys
import logging
from pathlib import Path

# 1. Suppress standard logging
logging.basicConfig(level=logging.ERROR)
logging.getLogger().setLevel(logging.ERROR)

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

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
from app.models.responses import BuildingResponse

# 2. Suppress loguru logging (used by the backend) - Done after imports to override backend config
try:
    from loguru import logger
    logger.remove() # Remove all existing handlers (including INFO console)
    logger.add(sys.stderr, level="ERROR") # Re-add only for ERROR and above
except ImportError:
    pass

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on the Earth."""
    R = 6371.0  # Earth radius in km
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c

async def preload_data():
    """Preload the dataset into memory."""
    dataset_path = Path(settings.DATASET_FULL)
    if dataset_path.exists():
        df = load_and_merge_data(str(dataset_path))
        
        # Populate caches to avoid disk loading with relative paths
        RealEstateService._dataset_cache["full"] = df
        analysis_service._base_dataset_cache["full"] = df
        
        if "id" in df.columns:
            df_indexed = df.copy()
            df_indexed["id_str"] = df_indexed["id"].astype(str)
            df_indexed = df_indexed.drop_duplicates(subset=["id_str"])
            df_indexed.set_index("id_str", inplace=True)
            RealEstateService._dataset_indexed_cache["full"] = df_indexed
    return True

def get_building_category(building: BuildingResponse) -> str:
    """Classify building by meta and ape status."""
    is_meta = bool(building.meta_immobile) or bool(building.meta_building)
    has_ape = (building.ape_files is not None and len(building.ape_files) > 0) or \
              (building.ape_scores is not None)
    
    meta_str = "yes_meta" if is_meta else "no_meta"
    ape_str = "yes_ape" if has_ape else "no_ape"
    return f"{meta_str}_{ape_str}"

async def run_single_test(agent_name: str, prompt: str, num_tries: int = 1):
    """Run the analysis and collect rankings."""
    print(f"[LANCIO] Agent: {agent_name} | Prompt: {prompt}")
    
    tries_rankings = []
    all_buildings_seen = {} # id -> BuildingResponse
    extra_info = {}
    
    for i in range(num_tries):
        try:
            run_id = f"test_{agent_name}_{datetime.now().strftime('%H%M%S')}_{i+1}"
            
            result = await analysis_service.run_analysis(
                run_id=run_id,
                query=prompt,
                dataset_key="full",
                map_limit=15000,
                llm_limit=25,
                analysis_mode="agent"
            )
            
            buildings = result.get("buildings", [])
            
            # Extract POI name from first run (or update if available)
            if agent_name == "location_agent" and "poi_name" not in extra_info and result.get("location"):
                locs = result.get("location")
                if locs and len(locs) > 0:
                    extra_info["poi_name"] = locs[0][0]
                    if len(locs[0]) >= 3:
                        extra_info["agent_poi_coords"] = [locs[0][1], locs[0][2]]
            
            # Extract APE requirements from first run
            if agent_name == "ape_agent" and "ape_requirements" not in extra_info:
                responses = result.get("gemini_responses", {})
                ape_analysis = responses.get("ape_analysis", {})
                if ape_analysis.get("found"):
                    extra_info["ape_requirements"] = ape_analysis.get("requisiti", [])

            # Extract activated agents from trace
            if "activated_agents" not in extra_info:
                trace = result.get("agent_trace", [])
                # Infrastructure agents that are always allowed/expected
                infra_agents = ["ranking", "sql", "evaluation", "relaxation", "broker"]
                active = []
                for entry in trace:
                    name = entry.get("agent_name", "")
                    if name:
                        clean_name = name.replace("-agent", "").lower()
                        # Skip if it is an infrastructure agent
                        is_infra = any(infra in clean_name for infra in infra_agents)
                        if not is_infra and clean_name not in active:
                            active.append(clean_name)
                extra_info["activated_agents"] = active
            
            # Extract final SQL query
            if "final_sql" not in extra_info:
                extra_info["final_sql"] = result.get("filters_applied", {}).get("final_sql", "")
            
            # Extract all gemini responses for all agents
            if "gemini_responses" not in extra_info:
                extra_info["gemini_responses"] = result.get("gemini_responses", {})

            # Extract full agent trace for results
            if "agent_trace" not in extra_info:
                extra_info["agent_trace"] = result.get("agent_trace", [])
            
            scores = {} # id -> score
            for b in buildings:
                scores[b.id] = b.score
                if b.id not in all_buildings_seen:
                    all_buildings_seen[b.id] = b
            
            tries_rankings.append(scores)
            
        except Exception:
            tries_rankings.append({})
            
    print(f"[FINE]   Agent: {agent_name} | Prompt: {prompt}")
    return tries_rankings, all_buildings_seen, extra_info

def _get_global_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate min/max and percentiles for all numeric columns in dataset."""
    stats = {}
    if df is None:
        return stats
    for col in df.columns:
        try:
            # Only for columns likely used in ranking
            if any(x in col for x in ["ape", "score", "sanita", "mobilita", "verde", "sport", "commerciale", "educazione", "epglnren"]):
                vals = pd.to_numeric(df[col], errors='coerce').dropna()
                if not vals.empty:
                    stats[col] = {
                        "min": float(vals.min()),
                        "max": float(vals.max()),
                        "median": float(vals.median()),
                        "p75": float(vals.quantile(0.75))
                    }
        except Exception:
            continue
    return stats

def calculate_gt_score(building_data: Dict[str, Any], strategy: Dict[str, Any], global_stats: Dict[str, Any] = None) -> float:
    """Calculate Ground Truth score based on JSON strategy."""
    if not strategy:
        return 0.0
        
    st_type = strategy.get("type")
    col = strategy.get("column")
    
    if st_type == "distance_decay":
        dist = building_data.get("dist_km")
        if dist is None or pd.isna(dist):
            return 0.0
        
        threshold = strategy.get("radius_reference", 2.5)
        
        if "radius_reference" in strategy and dist > threshold:
            return 0.0

        decay_constant = (-np.log(0.2))**(1/3)
        radius = threshold / decay_constant
        
        dist_rounded = round(dist, 2)
        return float(round(100 * np.exp(-(dist_rounded / radius)**3), 1))
    
    elif st_type == "mapping":
        val = str(building_data.get(col, "")).upper().strip()
        mapping = strategy.get("mapping", {})
        return float(mapping.get(val, 0.0))
    
    elif st_type == "greater_than":
        # Binary threshold strategy
        val = building_data.get(col)
        if val is None or pd.isna(val) or val == "N/D":
            return 0.0
        
        try:
            val_f = float(val)
            threshold = strategy.get("threshold", 0.0)
            exclusive = strategy.get("exclusive", False)
            
            if exclusive:
                return 100.0 if val_f > threshold else 0.0
            return 100.0 if val_f >= threshold else 0.0
        except:
            return 0.0

    elif st_type in ["linear_decay", "min_max"]:
        val = building_data.get(col)
        if val is None or pd.isna(val):
            return 0.0

        threshold = strategy.get("threshold")
        order = strategy.get("order", "desc")
        exclusive = strategy.get("exclusive", False)

        if threshold is not None:
            try:
                T = float(threshold)
                if order == "desc": # higher is better
                    # Score 0 at T, Score 100 at 2T
                    if T > 0:
                        score = ((val - T) / T * 100)
                    else:
                        score = 100.0
                    
                    if exclusive and val <= T: score = 0.0
                    elif val < T: score = 0.0
                    else: score = max(score, 0.1) # Ensure min 0.1 if >= T
                else: # asc (lower is better)
                    # Score 0 at T, Score 100 at T/2
                    if T > 0:
                        score = ((T - val) / (T / 2) * 100)
                    else:
                        score = 100.0 if val <= 0 else 0.0
                    
                    if exclusive and val >= T: score = 0.0
                    elif val > T: score = 0.0
                    else: score = max(score, 0.1) # Ensure min 0.1 if <= T
                
                return float(round(np.clip(score, 0, 100), 1))
            except Exception:
                pass

        # Fallback to standard min-max if no threshold provided
        stats = global_stats.get(col) if global_stats else None
        if not stats:
            return 0.0
        
        v_min = stats.get("min", 0)
        v_max = stats.get("max", 1)
        
        if v_max <= v_min:
            score = 100.0 if (order == "desc" and val >= v_min) or (order == "asc" and val <= v_max) else 0.0
        else:
            if order == "desc": # higher is better
                score = (val - v_min) / (v_max - v_min) * 100
            else: # asc (lower is better)
                score = (v_max - val) / (v_max - v_min) * 100
        
        return float(round(np.clip(score, 0, 100), 1))
    
    elif st_type == "energy_class":
        col = strategy.get("column", "classe_energetica_ape")
        val = str(building_data.get(col, "")).upper().strip()
        classes_order = ["A4", "A3", "A2", "A1", "B", "C", "D", "E", "F", "G"]
        
        if val not in classes_order:
            return 0.0
            
        allowed_classes = strategy.get("allowed_classes")
        if allowed_classes:
            allowed_classes_clean = [str(c).upper().strip() for c in allowed_classes]
            if val not in allowed_classes_clean:
                return 0.0
                
        min_class = strategy.get("min_class")
        if min_class:
            min_class = str(min_class).upper().strip()
            if min_class in classes_order:
                if classes_order.index(val) > classes_order.index(min_class):
                    return 0.0
        
        idx = classes_order.index(val)
        score = 100.0 * (1 - idx / (len(classes_order) - 1))
        return float(round(score, 1))

    elif st_type == "exact_match":
        val = str(building_data.get(col, "")).lower().replace(";", ",")
        target = str(strategy.get("value", "")).lower().replace(";", ",")
        if target in val or val in target:
            return 100.0
        return 0.0

    return 0.0

def generate_files(root_path: Path, agent_name: str, prompt: str, tries_rankings: List[Dict], buildings_info: Dict[str, BuildingResponse], extra_info: Dict[str, Any], columns: List[str], gt_strategy: Dict[str, Any] = None, expected_agents: List[str] = None):
    """Generate the output CSV files with score_gt."""
    # Truncate prompt for directory name to avoid "File name too long" error
    prompt_slug = prompt.replace("/", "_")[:100]
    prompt_dir = root_path / "results" / agent_name / prompt_slug
    prompt_dir.mkdir(parents=True, exist_ok=True)
    
    with open(prompt_dir / "prompt.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
    
    
    # Write final SQL query
    if extra_info.get("final_sql"):
        with open(prompt_dir / "final_query.sql", "w", encoding="utf-8") as f:
            f.write(extra_info["final_sql"])
    
    # Write Agent Responses
    responses = extra_info.get("gemini_responses", {})
    if responses:
        resp_dir = prompt_dir / "agent_responses"
        if resp_dir.exists():
            import shutil
            shutil.rmtree(resp_dir)
        resp_dir.mkdir(exist_ok=True)
        for agent_key, resp_data in responses.items():
            # Save only structured data (dictionaries) to avoid noise
            if isinstance(resp_data, dict):
                with open(resp_dir / f"{agent_key}.json", "w", encoding="utf-8") as f:
                    json.dump(resp_data, f, indent=2, ensure_ascii=False)
    
    
    # Agent Verification (considering only those who actually FOUND something)
    found_agents = []
    responses = extra_info.get("gemini_responses", {})
    
    # Check each agent for "found" status or data
    # 1. Location
    loc_resp = responses.get("location_extraction", {})
    if loc_resp.get("places") and len(loc_resp["places"]) > 0:
        found_agents.append("location")
    
    # 2. Property Technical
    typ_resp = responses.get("property_technical_extraction", {})
    if typ_resp.get("typologies") and len(typ_resp["typologies"]) > 0:
        found_agents.append("property_technical")
        
    # 3. Normative
    norm_resp = responses.get("normative_analysis", {})
    if norm_resp.get("found"):
        found_agents.append("normative")
        
    # 4. POI
    poi_resp = responses.get("poi_analysis", {})
    if poi_resp.get("found"):
        found_agents.append("poi")
        
    # 5. APE
    ape_resp = responses.get("ape_analysis", {})
    if ape_resp.get("found"):
        found_agents.append("ape")

    actual_agents = found_agents
    if expected_agents:
        # Compare sets to ignore order
        match = set(actual_agents) == set(expected_agents)
        verification = {
            "expected": expected_agents,
            "actual": actual_agents,
            "match": match,
            "missing": list(set(expected_agents) - set(actual_agents)),
            "extra": list(set(actual_agents) - set(expected_agents))
        }
        with open(prompt_dir / "agent_verification.json", "w", encoding="utf-8") as f:
            json.dump(verification, f, indent=2)
        
        status_str = "✅ MATCH" if match else "❌ MISMATCH"
        print(f"[CHECK]  Agents with results: {status_str} | Expected: {expected_agents} | Actual: {actual_agents}")
    
    # Calculate Ground Truth
    df_full = RealEstateService._dataset_cache.get("full")
    global_stats = _get_global_stats(df_full)
    id_to_gt_score = {}
    id_to_dist = {}
    
    if gt_strategy and df_full is not None:
        # Support both single strategy (dict) and multiple strategies (list)
        strategies = gt_strategy if isinstance(gt_strategy, list) else [gt_strategy]
        
        # Initialize temp dataframe for vectorized calculations
        temp_df = df_full.copy()
        temp_df["score_gt_combined"] = 0.0
        
        # Mask to track if all components are non-zero (for combined strategies)
        is_multi_strategy = isinstance(gt_strategy, list) and len(gt_strategy) > 1
        if is_multi_strategy:
            temp_df["all_components_nonzero"] = True
        
        # Calculate weights: use provided weights or default to equal distribution
        weights_specified = [s.get("weight") for s in strategies if "weight" in s]
        if len(weights_specified) == len(strategies):
            total_weight = sum(weights_specified)
            weights = [w / total_weight for w in weights_specified]
        else:
            weights = [1.0 / len(strategies)] * len(strategies)

        cols = list(df_full.columns)
        lat_col = next((c for c in ["latitudine", "lat", "latitude", "coordinata_y"] if c in cols), None)
        lon_col = next((c for c in ["longitudine", "lon", "longitude", "coordinata_x"] if c in cols), None)

        from app.data.loaders import get_coordinates

        for i, s in enumerate(strategies):
            weight = weights[i]
            s_type = s.get("type")
            
            if s_type == "distance_decay":
                poi_name = s.get("poi")
                lat_p, lon_p = get_coordinates(poi_name)
                
                if lat_p is not None and lon_p is not None and lat_col and lon_col:
                    temp_df["temp_dist"] = haversine(lat_p, lon_p, temp_df[lat_col].values, temp_df[lon_col].values)
                    threshold = s.get("radius_reference", 2.5)
                    decay_constant = (-np.log(0.2))**(1/3)
                    rad = threshold / decay_constant
                    
                    # Rounding to match agent logic (consistent with haversine use elsewhere)
                    s_scores = temp_df["temp_dist"].apply(lambda x: round(100 * np.exp(-(round(x, 2) / rad)**3), 1))
                    
                    if "radius_reference" in s:
                        s_scores.loc[temp_df["temp_dist"] > threshold] = 0.0
                    
                    temp_df["score_gt_combined"] += s_scores * weight
                    if is_multi_strategy:
                        temp_df["all_components_nonzero"] &= (s_scores > 0)
                    
                    # Store distance only for the first distance-based strategy found
                    if not id_to_dist:
                        id_to_dist = {str(k): v for k, v in temp_df.set_index("id")["temp_dist"].to_dict().items()}
                else:
                    # Fallback if geocoding fails
                    s_scores = temp_df.apply(lambda row: calculate_gt_score(row.to_dict(), s, global_stats), axis=1)
                    temp_df["score_gt_combined"] += s_scores * weight
                    if is_multi_strategy:
                        temp_df["all_components_nonzero"] &= (s_scores > 0)
            else:
                # Generic strategy
                s_scores = temp_df.apply(lambda row: calculate_gt_score(row.to_dict(), s, global_stats), axis=1)
                temp_df["score_gt_combined"] += s_scores * weight
                if is_multi_strategy:
                    temp_df["all_components_nonzero"] &= (s_scores > 0)

        # Apply the "AND" logic: if it's a combined execution, all components must be non-zero
        if is_multi_strategy:
            temp_df.loc[~temp_df["all_components_nonzero"], "score_gt_combined"] = 0.0

        id_to_gt_score = {str(k): round(float(v), 1) for k, v in temp_df.set_index("id")["score_gt_combined"].to_dict().items()}

    # Collect all buildings that appeared in ANY run OR have a non-zero GT score
    unique_ids = set()
    for run in tries_rankings:
        unique_ids.update(str(k) for k in run.keys())
    
    # Also include false negatives (GT > 0 but agent missed them)
    for bid, gt_val in id_to_gt_score.items():
        if isinstance(gt_val, (int, float)) and gt_val > 0:
            unique_ids.add(str(bid))
        
    merged_data = []
    for bid in unique_ids:
        gt_score = id_to_gt_score.get(bid, 0.0)
        if isinstance(gt_score, (int, float)):
            gt_score = round(float(gt_score), 1)
            
        dist_val = id_to_dist.get(bid, "-")
        if isinstance(dist_val, (int, float)):
            dist_val = round(float(dist_val), 3)
            
        # Agent score (ranks) - use 0.0 if excluded by SQL/system
        agent_scores = []
        for run in tries_rankings:
            val = run.get(bid)
            if val is None:
                val = run.get(int(bid) if bid.isdigit() else bid, 0.0)
            agent_scores.append(val)

        merged_data.append({
            "id": bid,
            "score_gt": gt_score,
            "dist_km": dist_val,
            "ranks": agent_scores
        })
        
    # Sort by GT Score (descending)
    def sort_key(x):
        gt = x["score_gt"]
        s1 = x["ranks"][0]
        gt_val = -float(gt) if isinstance(gt, (int, float)) else 1 # push non-numeric to bottom
        s_val = -float(s1) if isinstance(s1, (int, float)) else 1
        return (gt_val, s_val)

    merged_data.sort(key=sort_key)

    with open(prompt_dir / "results.csv", "w", encoding="utf-8") as f:
        # Define mandatory columns
        base_cols = ["id"]
        # Filter out mandatory columns if they were accidentally included in the JSON list
        extra_cols = [c for c in columns if c not in ["id", "id_immobile", "score_gt", "score", "score_agent"]]
        score_cols = ["score_gt", "score"]
        
        full_columns = base_cols + extra_cols + score_cols
        f.write(",".join(full_columns) + "\n")

        for item in merged_data:
            bid = item["id"]
            s_agent = item["ranks"][0]
            formatted_agent = str(round(float(s_agent), 1)) if isinstance(s_agent, (int, float)) else str(s_agent)
            
            row_vals = []
            for col in full_columns:
                if col in ["id", "id_immobile"]:
                    row_vals.append(str(bid))
                elif col == "score_gt":
                    row_vals.append(str(item["score_gt"]))
                elif col == "dist_km":
                    row_vals.append(str(item["dist_km"]))
                elif col in ["score", "score_agent"]:
                    row_vals.append(formatted_agent)
                else:
                    # Dynamic extraction from BuildingResponse
                    b_obj = buildings_info.get(bid)
                    val = "-"
                    if b_obj:
                        val_raw = getattr(b_obj, col, "-")
                        if val_raw is None:
                            val = "-"
                        elif hasattr(val_raw, "model_dump"):
                            val = json.dumps(val_raw.model_dump()).replace(",", ";")
                        elif isinstance(val_raw, (dict, list)):
                            val = json.dumps(val_raw).replace(",", ";")
                        else:
                            val = str(val_raw).replace(",", ";").replace("\n", " ")
                    row_vals.append(val)

            f.write(",".join(row_vals) + "\n")

async def main():
    suite_dir = Path(__file__).parent
    
    # Check for composed_queries.csv logic first as requested
    queries_csv = suite_dir / "composed_queries.csv"
    if queries_csv.exists():
        print(f"[LOAD] Processing queries from: {queries_csv.name}")
        output_dir = suite_dir / "composed_results"
        output_dir.mkdir(exist_ok=True)
        
        # Load CSV with pandas
        df_queries = pd.read_csv(queries_csv)
        
        # We only process queries with status 0
        pending_mask = df_queries["status"] == 0
        pending_queries = df_queries[pending_mask].index.tolist()
        
        if not pending_queries:
            print("[INFO] No pending queries to process (all status != 0).")
            return

        await preload_data()
        # limit concurrency to avoid overloading
        semaphore = asyncio.Semaphore(5)
        csv_lock = asyncio.Lock()
        
        async def process_query(idx):
            query = df_queries.at[idx, "query"]
            async with semaphore:
                agent = "graph_orchestrator"
                try:
                    tries, b_info, extra_info = await run_single_test(agent, query)
                    
                    agent_results = []
                    for t in extra_info.get("agent_trace", []):
                        name = t.get("agent_name", "")
                        mode = t.get("agent_mode", "filtering")
                        
                        if mode == "ranking" or name == "evaluation-agent":
                            continue
                            
                        agent_results.append({
                            "agent_name": name,
                            "execution_time_ms": round(t.get("execution_time_ms", 0), 2),
                            "output": t.get("output")
                        })
                    
                    ranking = []
                    if tries and tries[0]:
                        # Sort by score descending
                        sorted_items = sorted(tries[0].items(), key=lambda x: x[1], reverse=True)
                        for bid, score in sorted_items:
                            ranking.append({
                                "id": str(bid),
                                "score": float(round(score, 1))
                            })

                    result_json = {
                        "query": query,
                        "final_query": extra_info.get("final_sql", ""), # Alias requested by user
                        "final_sql": extra_info.get("final_sql", ""),
                        "ranking": ranking,
                        "agent_results": agent_results
                    }
                    
                    # Save each query to its own JSON file
                    output_file = output_dir / f"query_{idx+1:03d}.json"
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(result_json, f, indent=4, ensure_ascii=False)
                    
                    # Update status to 1 (Success)
                    async with csv_lock:
                        df_queries.at[idx, "status"] = 1
                        df_queries.to_csv(queries_csv, index=False)
                        
                except Exception as e:
                    print(f"[ERROR] Query {idx+1} failed: {e}")
                    # Update status to 2 (Error)
                    async with csv_lock:
                        df_queries.at[idx, "status"] = 2
                        df_queries.to_csv(queries_csv, index=False)

        tasks = [process_query(idx) for idx in pending_queries]
        if tasks:
            print(f"[INFO] Starting {len(tasks)} pending queries...")
            await asyncio.gather(*tasks)
            print(f"[SUCCESS] Updated statuses in {queries_csv.name}")
        return

    # DEPRECATED: Fallback to composed_queries.txt if CSV doesn't exist
    queries_file = suite_dir / "composed_queries.txt"
    if queries_file.exists():
        print(f"[LOAD] Processing queries from: {queries_file.name}")
        output_dir = suite_dir / "composed_results"
        output_dir.mkdir(exist_ok=True)
        
        with open(queries_file, "r", encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]
        
        await preload_data()
        # limit concurrency to avoid overloading
        semaphore = asyncio.Semaphore(5)
        
        async def process_query(idx, query):
            async with semaphore:
                # Use graph_orchestrator for general composed queries
                agent = "graph_orchestrator"
                try:
                    # Run without multiple tries and without generating folders unless needed
                    tries, b_info, extra_info = await run_single_test(agent, query)
                    
                    agent_results = []
                    for t in extra_info.get("agent_trace", []):
                        name = t.get("agent_name", "")
                        mode = t.get("agent_mode", "filtering")
                        
                        if mode == "ranking" or name == "evaluation-agent":
                            continue
                            
                        agent_results.append({
                            "agent_name": name,
                            "execution_time_ms": round(t.get("execution_time_ms", 0), 2),
                            "output": t.get("output")
                        })
                    
                    result_json = {
                        "query": query,
                        "final_sql": extra_info.get("final_sql", ""),
                        "agent_results": agent_results
                    }
                    
                    # Save each query to its own JSON file
                    output_file = output_dir / f"query_{idx+1:03d}.json"
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(result_json, f, indent=4, ensure_ascii=False)
                        
                except Exception as e:
                    print(f"[ERROR] Query {idx+1} failed: {e}")

        tasks = [process_query(i, q) for i, q in enumerate(queries)]
        if tasks:
            print(f"[INFO] Starting {len(tasks)} queries...")
            await asyncio.gather(*tasks)
            print(f"[SUCCESS] Saved {len(queries)} JSON results to {output_dir}")
        return

    # Fallback to existing logic for custom_test_case.json
    input_file = suite_dir / "custom_test_case.json"
    
    if not input_file.exists():
        print(f"Error: {input_file.name} not found in {suite_dir}.")
        return
    
    await preload_data()
    semaphore = asyncio.Semaphore(5)
    
    async def run_task_wrapper(entry):
        async with semaphore:
            agent = entry.get("agent") or entry.get("agent_name")
            if not agent:
                exp = entry.get("expected_agents", [])
                if len(exp) > 1:
                    agent = "graph_orchestrator"
                elif len(exp) == 1:
                    agent = f"{exp[0]}_agent"
                else:
                    agent = "generic_agent"
            
            query = entry.get("query", "")
            tries, b_info, extra_info = await run_single_test(agent, query)
            
            agent_results = []
            for t in extra_info.get("agent_trace", []):
                name = t.get("agent_name", "")
                mode = t.get("agent_mode", "filtering")
                if mode == "ranking" or name == "evaluation-agent":
                    continue
                    
                agent_results.append({
                    "agent_name": name,
                    "execution_time_ms": round(t.get("execution_time_ms", 0), 2),
                    "output": t.get("output")
                })
            
            entry["agent_results"] = agent_results
            for k in ["agent", "agent_name_redundant", "final_sql"]:
                if k in entry:
                    del entry[k]

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        tasks = []
        if isinstance(data, list):
            print(f"[LOAD] Processing: {input_file.name}")
            for entry in data:
                if not isinstance(entry, dict) or not entry.get("active", True):
                    continue
                tasks.append(run_task_wrapper(entry))
        
        if tasks:
            print(f"[INFO] Starting {len(tasks)} tests from {input_file.name}...")
            await asyncio.gather(*tasks)
            with open(input_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"[SUCCESS] Updated {input_file.name} with agent results.")
        else:
            print(f"[INFO] No active tests found in {input_file.name}.")

    except Exception as e:
        print(f"[ERROR] Failed to process {input_file.name}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
