
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
                # Filter out ranking-agent and SQL as they are infrastructure
                # Map names like 'location-agent' to 'location'
                active = []
                for entry in trace:
                    name = entry.get("agent_name", "")
                    if name and name not in ["ranking-agent"]:
                        clean_name = name.replace("-agent", "")
                        if clean_name not in active:
                            active.append(clean_name)
                extra_info["activated_agents"] = active
            
            # Extract final SQL query
            if "final_sql" not in extra_info:
                extra_info["final_sql"] = result.get("filters_applied", {}).get("final_sql", "")
            
            # Extract location threshold
            if agent_name == "location_agent" and "location_threshold" not in extra_info:
                responses = result.get("gemini_responses", {})
                loc_ext = responses.get("location_extraction", {})
                places = loc_ext.get("places", [])
                if places:
                    # If multiple, take the first one (most common case) or list them
                    thresholds = [str(p.get("radius_km", "3.0")) for p in places]
                    extra_info["location_threshold"] = ", ".join(thresholds)

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
                else: # asc (lower is better)
                    # Score 0 at T, Score 100 at T/2
                    if T > 0:
                        score = ((T - val) / (T / 2) * 100)
                    else:
                        score = 100.0 if val <= 0 else 0.0
                    
                    if exclusive and val >= T: score = 0.0
                    elif val > T: score = 0.0
                
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
        val = str(building_data.get(col, "")).lower()
        target = str(strategy.get("value", "")).lower()
        if target in val or val in target:
            return 100.0
        return 0.0

    return 0.0

def generate_files(root_path: Path, agent_name: str, prompt: str, tries_rankings: List[Dict], buildings_info: Dict[str, BuildingResponse], extra_info: Dict[str, Any], columns: List[str], gt_strategy: Dict[str, Any] = None):
    """Generate the output CSV files with score_gt."""
    prompt_dir = root_path / "results" / agent_name / prompt.replace("/", "_")
    prompt_dir.mkdir(parents=True, exist_ok=True)
    
    with open(prompt_dir / "prompt.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
    
    # Write activated agents
    with open(prompt_dir / "activated_agents.txt", "w", encoding="utf-8") as f:
        agents = extra_info.get("activated_agents", [])
        f.write("\n".join(agents))
    
    # Write final SQL query
    if extra_info.get("final_sql"):
        with open(prompt_dir / "final_query.sql", "w", encoding="utf-8") as f:
            f.write(extra_info["final_sql"])
    
    # Write location threshold
    if agent_name == "location_agent" and extra_info.get("location_threshold"):
        with open(prompt_dir / "location_threshold.txt", "w", encoding="utf-8") as f:
            f.write(extra_info["location_threshold"])
    
    # Calculate Ground Truth
    df_full = RealEstateService._dataset_cache.get("full")
    global_stats = _get_global_stats(df_full)
    id_to_gt_score = {}
    id_to_dist = {}
    
    # Pre-calculate coordinates for distance_decay strategy
    lat_p, lon_p = None, None
    if gt_strategy and gt_strategy.get("type") == "distance_decay" and df_full is not None:
        poi_name = gt_strategy.get("poi")
        from app.data.loaders import get_coordinates
        lat_p, lon_p = get_coordinates(poi_name)

    # Removed saving of poi_coordinates.json as requested

    
    # Calculate GT scores for all relevant strategies
    if gt_strategy and df_full is not None:
        cols = list(df_full.columns)
        lat_col = next((c for c in ["latitudine", "lat", "latitude", "coordinata_y"] if c in cols), None)
        lon_col = next((c for c in ["longitudine", "lon", "longitude", "coordinata_x"] if c in cols), None)
        
        # Fast path for location decay
        if gt_strategy.get("type") == "distance_decay" and lat_p is not None and lon_p is not None and lat_col and lon_col:
            temp_df = df_full.dropna(subset=[lat_col, lon_col]).copy()
            temp_df["dist_km"] = haversine(lat_p, lon_p, temp_df[lat_col].values, temp_df[lon_col].values)
            
            threshold = gt_strategy.get("radius_reference", 2.5)
            # Calculate R such that score is 20 (0.2) at threshold
            decay_constant = (-np.log(0.2))**(1/3) # approx 1.172
            rad = threshold / decay_constant
            
            # Calculate score using rounded distance to match agent's logic, but cutoff uses precise distance
            temp_df["score_gt"] = temp_df["dist_km"].apply(lambda x: round(100 * np.exp(-(round(x, 2) / rad)**3), 1))
            
            # Enforce hard cutoff if radius_reference is specified
            if "radius_reference" in gt_strategy:
                temp_df.loc[temp_df["dist_km"] > threshold, "score_gt"] = 0.0

            id_to_gt_score = {str(k): v for k, v in temp_df.set_index("id")["score_gt"].to_dict().items()}
            id_to_dist = {str(k): v for k, v in temp_df.set_index("id")["dist_km"].to_dict().items()}
        else:
            # Generic strategy (mapping, min_max, exact_match)
            temp_df = df_full.copy()
            temp_df["score_gt"] = temp_df.apply(lambda row: calculate_gt_score(row.to_dict(), gt_strategy, global_stats), axis=1)
            id_to_gt_score = {str(k): v for k, v in temp_df.set_index("id")["score_gt"].to_dict().items()}

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
    input_file = suite_dir / "agents_prompts.json"
    
    if not input_file.exists():
        print(f"Error: {input_file} not found.")
        return
    
    with open(input_file, "r") as f:
        tests_dict = json.load(f)
    
    await preload_data()
    
    # Use a semaphore to limit concurrency and avoid hitting LLM rate limits or OOM
    semaphore = asyncio.Semaphore(3)
    
    async def run_task(agent, query, cols, gt_strategy):
        async with semaphore:
            tries, b_info, extra_info = await run_single_test(agent, query)
            generate_files(suite_dir, agent, query, tries, b_info, extra_info, cols, gt_strategy)

    tasks = []
    for agent, agent_data in tests_dict.items():
        # Support new structure with "prompts" key
        if isinstance(agent_data, dict) and "prompts" in agent_data:
            prompts = agent_data["prompts"]
        else:
            # Legacy support (list of prompts)
            prompts = agent_data

        for prompt_data in prompts:
            if isinstance(prompt_data, str):
                query = prompt_data
                columns = []
                gt_strategy = None
                active = True
            else:
                active = prompt_data.get("active", True)
                query = prompt_data["query"]
                columns = prompt_data.get("columns", [])
                gt_strategy = prompt_data.get("gt_strategy")
            
            if not active:
                print(f"[SKIP] Prompt: {query[:50]}...")
                continue
                
            tasks.append(run_task(agent, query, columns, gt_strategy))
    
    # Run all tasks in parallel
    if tasks:
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
