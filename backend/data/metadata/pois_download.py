"""
Download and Format Data from Overpass API

This script downloads Point of Interest (POI) data using the OpenStreetMap Overpass API 
and formats it into a pandas DataFrame.
"""

import requests
import json
import pandas as pd
import os
import sys
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# --- Configuration & Paths ---
# Add backend root and script directory to sys.path
_script_dir = Path(__file__).resolve().parent
_backend_path = _script_dir.parent.parent
if str(_backend_path) not in sys.path:
    sys.path.append(str(_backend_path))
if str(_script_dir) not in sys.path:
    sys.path.append(str(_script_dir))
load_dotenv(_backend_path / ".env")

def get_env_path(var_name: str, default: str) -> str:
    path_str = os.getenv(var_name, default)
    # If it's a relative path, make it relative to the backend root
    path = Path(path_str)
    if not path.is_absolute():
        # Handle cases where the path might start with "backend/"
        if path_str.startswith("backend/"):
            path = _backend_path.parent / path
        else:
            path = _backend_path / path
    
    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)

# Parametrized paths from environment
query_file = get_env_path("POI_QUERY_FILE", "data/metadata/pois_query.txt")
data_file = get_env_path("POI_RAW_DATA_FILE", "data/metadata/pois.json")
output_file = get_env_path("POI_PATH", "data/metadata/pois_by_category.json")
if os.path.exists(query_file):
    with open(query_file, 'r') as file:
        pois_query = file.read()
    print("Query loaded successfully.")
    print(pois_query[:200] + "..." if len(pois_query) > 200 else pois_query)
else:
    print(f"Error: {query_file} not found.")
    pois_query = None

# --- Fetch Data ---
# Send the request to Overpass API or load from an existing local file.


if os.path.exists(data_file):
    print(f"File {data_file} already exists, loading local data.")
    with open(data_file, 'r') as f:
        data = json.load(f)
else:
    if pois_query:
        overpass_url = "https://overpass-api.de/api/interpreter"
        headers = {"User-Agent": "OSM-Extraction-Script/1.2 (https://github.com/openstreetmap)"}
        print("Downloading data from Overpass API... (this might take a while)")
        response = requests.post(overpass_url, data={'data': pois_query}, headers=headers)

        if response.status_code == 200:
            data = response.json()
            print("Data downloaded successfully.")
            # Save for future use
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Data saved to {data_file}")
        else:
            print(f"Request error: {response.status_code}")
            print(f"Response details: {response.text}")
            data = None
    else:
        print("No query available to fetch data.")
        data = None

# --- Process and Format Data ---
# Import configurations and process the raw OSM elements into a structured DataFrame.

# Import amenity configurations
try:
    from amenities_config import CATEGORIES, CATEGORY_AMENITIES
except ImportError:
    print("Warning: Could not import configs from amenities_config.py. Using defaults.")
    CATEGORIES = []
    CATEGORY_AMENITIES = {}

def clean_amenity_value(value: Any) -> Any:
    """Extracts the first part of a semicolon-separated OSM tag value."""
    if not isinstance(value, str):
        return value
    return value.split(';', 1)[0].strip()

def round_coord(value: Optional[float]) -> Optional[float]:
    """Rounds coordinates to 7 decimal places."""
    if value is None:
        return None
    return round(value, 7)

def get_category_amenity(tags: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    """Identifies category and amenity type based on OSM tags and configuration."""
    tags = tags or {}
    for category, amenities in CATEGORY_AMENITIES.items():
        for amenity_key, amenity_value in amenities:
            # Match specific value or wildcard (*)
            if (amenity_value == '*' and amenity_key in tags) or tags.get(amenity_key) == amenity_value:
                actual_value = tags.get(amenity_key) if amenity_value == '*' else amenity_value
                actual_value = clean_amenity_value(actual_value)
                return category, actual_value
    return None, None

def is_placeholder_amenity(value: Optional[str]) -> bool:
    """Checks if the amenity value is just 'yes', which is often a non-specific placeholder."""
    return value == 'yes'

if data:
    elements = data.get('elements', [])
    
    # Map elements by ID for easy lookup
    nodes = {elem['id']: elem for elem in elements if elem['type'] == 'node'}
    ways = {elem['id']: elem for elem in elements if elem['type'] == 'way'}
    relations = {elem['id']: elem for elem in elements if elem['type'] == 'relation'}
    
    formatted_pois = []
    used_node_ids = set()
    
    # 1. Process Nodes
    print("Processing nodes...")
    for nid, node in nodes.items():
        if node.get('lat') is not None and node.get('lon') is not None:
            tags = node.get('tags')
            if not tags:
                continue
            cat, am = get_category_amenity(tags)
            if not cat or is_placeholder_amenity(am):
                continue
            formatted_pois.append({
                'id': nid,
                'type': 'node',
                'lat': round_coord(node['lat']),
                'lon': round_coord(node['lon']),
                'category': cat,
                'amenity': am
            })
            used_node_ids.add(nid)
    
    # 2. Process Ways
    # ways are often building footprints or areas
    print("Processing ways...")
    for wid, way in ways.items():
        # Only use nodes that belong to this way and haven't been treated as individual POIs
        way_nodes = [nodes[nid] for nid in way.get('nodes', []) if nid in nodes and nodes[nid].get('lat') is not None]
        if not way_nodes:
            continue
            
        # Strategy: 
        # Check if tags are on the way itself. If not, check if they are consistent across its nodes.
        cat, am = get_category_amenity(way.get('tags', {}))
        
        if not cat or is_placeholder_amenity(am):
            # Fallback: check nodes within the way
            node_matches = []
            for n in way_nodes:
                n_cat, n_am = get_category_amenity(n.get('tags', {}))
                if n_cat and not is_placeholder_amenity(n_am):
                    node_matches.append((n_cat, n_am, n['id']))
            
            if node_matches:
                # If all nodes have the same category/amenity, use it
                sample_cat, sample_am, _ = node_matches[0]
                if all(m[0] == sample_cat and m[1] == sample_am for m in node_matches):
                    cat, am = sample_cat, sample_am
                    # Mark these nodes as used so we don't double count
                    for _, _, nid in node_matches:
                        used_node_ids.add(nid)
        
        if cat and not is_placeholder_amenity(am):
            lats = [n['lat'] for n in way_nodes]
            lons = [n['lon'] for n in way_nodes]
            formatted_pois.append({
                'id': wid,
                'type': 'way',
                'lat': round_coord(sum(lats) / len(lats)),
                'lon': round_coord(sum(lons) / len(lons)),
                'category': cat,
                'amenity': am
            })

    # 3. Process Relations
    print("Processing relations...")
    for rid, rel in relations.items():
        member_pois = []
        for member in rel.get('members', []):
            m_id = member['ref']
            if member['type'] == 'node' and m_id in nodes:
                n = nodes[m_id]
                m_cat, m_am = get_category_amenity(n.get('tags', {}))
                if m_cat and not is_placeholder_amenity(m_am):
                    member_pois.append({
                        'lat': n['lat'], 'lon': n['lon'], 'cat': m_cat, 'am': m_am
                    })
            elif member['type'] == 'way' and m_id in ways:
                w = ways[m_id]
                w_nodes = [nodes[nid] for nid in w.get('nodes', []) if nid in nodes and nodes[nid].get('lat') is not None]
                if w_nodes:
                    w_cat, w_am = get_category_amenity(w.get('tags', {}))
                    if w_cat and not is_placeholder_amenity(w_am):
                        lats = [n['lat'] for n in w_nodes]
                        lons = [n['lon'] for n in w_nodes]
                        member_pois.append({
                            'lat': sum(lats) / len(lats), 'lon': sum(lons) / len(lons), 'cat': w_cat, 'am': w_am
                        })
        
        if member_pois:
            # Inherit category/amenity from relation tags if available, else from members
            cat, am = get_category_amenity(rel.get('tags', {}))
            if not cat or is_placeholder_amenity(am):
                sample_cat, sample_am = member_pois[0]['cat'], member_pois[0]['am']
                if all(m['cat'] == sample_cat and m['am'] == sample_am for m in member_pois):
                    cat, am = sample_cat, sample_am
            
            if cat and not is_placeholder_amenity(am):
                lats = [m['lat'] for m in member_pois]
                lons = [m['lon'] for m in member_pois]
                formatted_pois.append({
                    'id': rid,
                    'type': 'relation',
                    'lat': round_coord(sum(lats) / len(lats)),
                    'lon': round_coord(sum(lons) / len(lons)),
                    'category': cat,
                    'amenity': am
                })

    df = pd.DataFrame(formatted_pois)
    # Remove duplicates if any (by ID)
    df = df.drop_duplicates(subset=['id'])
    print(f"DataFrame created with {len(df)} elements.")
    if not df.empty:
        print(df.head())
else:
    print("No data available to process.")
    df = pd.DataFrame()

# --- Data Cleaning ---
# Remove entries with missing coordinates.
if not df.empty:
    df = df.dropna(subset=['lat', 'lon'])
    print(f"After cleaning: {len(df)} elements remaining.")
else:
    print("No DataFrame available to clean.")

# --- Categorization ---
# Organize POIs into a hierarchical dictionary: {category: {amenity: [list_of_pois]}}.

if not df.empty:
    # Group pois by category and amenity for the final structure
    pois_by_category = df.groupby('category').apply(
        lambda x: x.groupby('amenity').apply(
            lambda y: y[['id', 'lat', 'lon']].to_dict('records')
        ).to_dict()
    ).to_dict()
    
    print("POIs categorized successfully.")
    for cat, amenities_dict in pois_by_category.items():
        total_cat = sum(len(pois) for pois in amenities_dict.values())
        print(f"{cat}: Total {total_cat} POIs")
        for amenity, pois in amenities_dict.items():
            print(f"  - {amenity}: {len(pois)}")
else:
    print("No DataFrame available to categorize.")
    pois_by_category = {}

# Serialize the categorized POIs to a JSON file.
if pois_by_category:
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(pois_by_category, f, indent=2, ensure_ascii=False)
    print(f"Categorized data saved to {output_file}")

# --- Relocations (Manual Adjustments) ---
# Sometimes POIs are tagged in a way that belongs better in another category for our analysis.

class Relocation:
    """Helper class to define category/amenity reassignment."""
    def __init__(self, from_cat, from_am, to_cat, to_am):
        self.from_cat = from_cat
        self.from_am = from_am
        self.to_cat = to_cat
        self.to_am = to_am

# Define the list of relocations
relocations = [
    Relocation(
        from_cat='commercial',
        from_am='swimming_pool',
        to_cat='sport',
        to_am='swimming_pool'
    )
]

def apply_relocations(poi_dict: Dict, relocation_list: List[Relocation]) -> Dict:
    """Applies the relocation rules to the nested POI dictionary."""
    for rule in relocation_list:
        if rule.from_cat in poi_dict and rule.from_am in poi_dict[rule.from_cat]:
            pois_to_move = poi_dict[rule.from_cat].pop(rule.from_am)
            
            if rule.to_cat not in poi_dict:
                poi_dict[rule.to_cat] = {}
            if rule.to_am not in poi_dict[rule.to_cat]:
                poi_dict[rule.to_cat][rule.to_am] = []
                
            poi_dict[rule.to_cat][rule.to_am].extend(pois_to_move)
            print(f"Moved {len(pois_to_move)} POIs from {rule.from_cat}/{rule.from_am} to {rule.to_cat}/{rule.to_am}")
    
    return poi_dict

if pois_by_category and relocations:
    pois_by_category = apply_relocations(pois_by_category, relocations)
    
    # Save updated data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(pois_by_category, f, indent=2, ensure_ascii=False)
    print(f"Updated data saved to {output_file}")

# --- Consistency Check ---
# Identify POIs present in the raw data but missing from the finalized categorized dictionary.
if not df.empty:
    # Get all IDs in the final categorized dictionary
    final_ids = set()
    for cat_dict in pois_by_category.values():
        for am_list in cat_dict.values():
            for poi in am_list:
                try:
                    final_ids.add(int(poi['id']))
                except (ValueError, TypeError):
                    pass
    
    df_ids = set(df['id'].astype(int))
    missing_ids = df_ids - final_ids
    
    print(f"Total POIs in DataFrame: {len(df_ids)}")
    print(f"Total POIs in Categorized Dict: {len(final_ids)}")
    print(f"Missing POIs: {len(missing_ids)}")
    
    if missing_ids:
        missing_df = df[df['id'].isin(missing_ids)]
        print("First missing elements:")
        print(missing_df.head())
        
        # Save missing IDs
        with open('missing_poi_ids.txt', 'w', encoding='utf-8') as f:
            for mid in sorted(missing_ids):
                f.write(f"{mid}\n")
        print(f"Saved missing IDs to missing_poi_ids.txt")

        # Detailed debugging for the first 50 missing items using raw data
        if os.path.exists('pois.json'):
            with open('pois.json', 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            raw_elements = {e['id']: e for e in raw_data.get('elements', [])}
            
            print("\nDebug info for missing items (first 5 missing):")
            for mid in list(sorted(missing_ids))[:5]:
                elem = raw_elements.get(mid)
                if elem:
                    print(f"ID: {mid} | Type: {elem.get('type')} | Tags: {elem.get('tags', {})}")
                else:
                    print(f"ID: {mid} not found in raw pois.json")
else:
    print("No DataFrame available for consistency check.")
