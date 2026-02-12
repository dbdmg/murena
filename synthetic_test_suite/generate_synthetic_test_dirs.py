
import asyncio
import json
import os
import pandas as pd
import numpy as np
import sys
from pathlib import Path
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
        print(f"Preloading dataset from {dataset_path}...")
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
        print(f"Dataset preloaded: {len(df)} rows")
    return True

def get_building_category(building: BuildingResponse) -> str:
    """Classify building by meta and ape status."""
    is_meta = bool(building.meta_immobile) or bool(building.meta_building)
    has_ape = (building.ape_files is not None and len(building.ape_files) > 0) or \
              (building.ape_scores is not None)
    
    meta_str = "yes_meta" if is_meta else "no_meta"
    ape_str = "yes_ape" if has_ape else "no_ape"
    return f"{meta_str}_{ape_str}"

async def run_single_test(agent_name: str, prompt: str, num_tries: int = 3):
    """Run the analysis 3 times and collect rankings."""
    print(f"\n🚀 Testing Agent: {agent_name} | Prompt: {prompt}")
    
    tries_rankings = []
    all_buildings_seen = {} # id -> BuildingResponse
    poi_coords = None
    
    for i in range(num_tries):
        print(f"  Try {i+1}/{num_tries}...", end=" ", flush=True)
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
            print(f"done ({len(buildings)} results)")
            
            # Extract POI coords from first run (or update if available)
            if not poi_coords and result.get("location"):
                # location format: [[name, lat, lon], ...]
                locs = result.get("location")
                if locs and len(locs) > 0 and len(locs[0]) >= 3:
                    poi_coords = (locs[0][1], locs[0][2])
            
            scores = {} # id -> score
            for b in buildings:
                scores[b.id] = b.score
                if b.id not in all_buildings_seen:
                    all_buildings_seen[b.id] = b
            
            tries_rankings.append(scores)
            
        except Exception as e:
            print(f"failed! {e}")
            tries_rankings.append({})
            
    return tries_rankings, all_buildings_seen, poi_coords

def generate_files(root_path: Path, agent_name: str, prompt: str, tries_rankings: List[Dict], buildings_info: Dict[str, BuildingResponse], poi_coords: Optional[Tuple[float, float]]):
    """Generate the output CSV files with rank_gt."""
    prompt_dir = root_path / "results" / agent_name / prompt.replace("/", "_")
    prompt_dir.mkdir(parents=True, exist_ok=True)
    
    with open(prompt_dir / "prompt.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
    
    # Calculate Ground Truth for location agent if we have coords
    df_full = RealEstateService._dataset_cache.get("full")
    
    # Identify actual columns in the dataset
    cols = list(df_full.columns) if df_full is not None else []
    lat_col = next((c for c in ["latitudine", "lat", "latitude", "coordinata_y"] if c in cols), None)
    lon_col = next((c for c in ["longitudine", "lon", "longitude", "coordinata_x"] if c in cols), None)
    
    real_estate_service = RealEstateService()
    id_to_dist = {}
    
    # Calculate Distances if it's the location agent
    if agent_name == "location_agent" and poi_coords and df_full is not None and lat_col and lon_col:
        lat_p, lon_p = poi_coords
        temp_df = df_full.copy()
        
        # Drop rows without coordinates
        temp_df = temp_df.dropna(subset=[lat_col, lon_col])
        
        if not temp_df.empty:
            # Calculate Distance for the entire dataset
            temp_df['gt_dist'] = haversine(temp_df[lat_col].values, temp_df[lon_col].values, lat_p, lon_p)
            # Create mapping id -> distance
            id_to_dist = dict(zip(temp_df['id'].astype(str), temp_df['gt_dist']))
            
            # Sort to identify the top 20 for GT inclusion (ensure they are in buildings_info)
            top_gt = temp_df.sort_values('gt_dist').head(20)
            for _, row in top_gt.iterrows():
                bid = str(row['id'])
                if bid not in buildings_info:
                    try:
                        buildings_info[bid] = real_estate_service._df_row_to_building(row)
                    except:
                        pass

    # Collect all buildings that appeared in ANY run or are in the top GT
    unique_ids = set()
    # Always include top 20 GT for location agent
    if agent_name == "location_agent" and id_to_dist:
        # Get ids of top 20 closest
        top_20_ids = sorted(id_to_dist.keys(), key=lambda x: id_to_dist[x])[:20]
        unique_ids.update(top_20_ids)
        
    for run in tries_rankings:
        unique_ids.update(run.keys())
        
    merged_data = []
    for bid in unique_ids:
        dist_val = id_to_dist.get(bid, "-")
        # Format distance to 3 decimal places if it's a number
        if isinstance(dist_val, (int, float)):
            dist_val = round(float(dist_val), 3)
            
        merged_data.append({
            "id": bid,
            "dist_gt": dist_val,
            "ranks": [(run.get(bid) if run.get(bid) is not None else "-") for run in tries_rankings]
        })
        
    # Sort by Distance (ascending) then by score (descending)
    def sort_key(x):
        d = x["dist_gt"]
        s1 = x["ranks"][0] # This is score_1 from run 1
        
        # Distance: lower is better (0 is best, 9999 is worst)
        d_val = float(d) if isinstance(d, (int, float)) else 9999
        # Score: higher is better (convert to negative for ascending sort: -100 is best, 0 is worst)
        s_val = -float(s1) if isinstance(s1, (int, float)) else 0
        
        return (d_val, s_val)

    merged_data.sort(key=sort_key)

    with open(prompt_dir / "results.csv", "w", encoding="utf-8") as f:
        f.write("id_immobile,dist_gt_km,score_1,score_2,score_3\n")
        for item in merged_data:
            # Round scores to 2 decimal places if they are numbers
            formatted_scores = []
            for s in item["ranks"]:
                if isinstance(s, (int, float)):
                    formatted_scores.append(str(round(float(s), 2)))
                else:
                    formatted_scores.append(str(s))
            
            scores_str = ",".join(formatted_scores)
            f.write(f"{item['id']},{item['dist_gt']},{scores_str}\n")

async def main():
    suite_dir = Path(__file__).parent
    input_file = suite_dir / "agents_prompts.json"
    
    if not input_file.exists():
        print(f"Error: {input_file} not found.")
        return
    
    with open(input_file, "r") as f:
        tests_dict = json.load(f)
    
    await preload_data()
    
    for agent, prompts in tests_dict.items():
        for prompt in prompts:
            tries, b_info, poi_coords = await run_single_test(agent, prompt)
            generate_files(suite_dir, agent, prompt, tries, b_info, poi_coords)

if __name__ == "__main__":
    asyncio.run(main())
