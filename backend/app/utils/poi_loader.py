import json
import os
from functools import lru_cache
import pandas as pd

# Define path relative to project root (assuming execution from project root)
POI_JSON_PATH = os.path.join("FOLDER_STATIC_ROME", "pois.json")

# Category definitions based on tags
CATEGORIES = {
    "verde": {
        "tags": {
            "leisure": ["park", "garden", "nature_reserve", "playground"],
            "landuse": ["grass", "forest", "recreation_ground"],
            "natural": ["tree", "wood"],
        },
        "color": "#4CAF50",  # Green
        "icon": "leaf",
    },
    "trasporti": {
        "tags": {
            "public_transport": ["stop_position", "platform", "station"],
            "highway": ["bus_stop"],
            "railway": ["station", "subway_entrance", "tram_stop"],
            "amenity": ["parking", "bicycle_parking"],
        },
        "color": "#2196F3",  # Blue
        "icon": "bus",
    },
    "istruzione": {
        "tags": {"amenity": ["school", "university", "kindergarten", "college", "library"]},
        "color": "#FF9800",  # Orange
        "icon": "graduation-cap",
    },
    "salute": {
        "tags": {
            "amenity": ["pharmacy", "hospital", "clinic", "doctors", "dentist"],
            "healthcare": ["pharmacy", "hospital", "doctor"],
        },
        "color": "#F44336",  # Red
        "icon": "medkit",
    },
    "commercio": {
        "tags": {
            "shop": [
                "supermarket",
                "convenience",
                "bakery",
                "clothes",
                "mall",
                "department_store",
            ]
        },
        "color": "#9C27B0",  # Purple
        "icon": "shopping-cart",
    },
    "cultura": {
        "tags": {
            "tourism": ["museum", "gallery", "artwork", "attraction"],
            "amenity": ["theatre", "cinema", "arts_centre"],
        },
        "color": "#E91E63",  # Pink
        "icon": "paint-brush",
    },
}


@lru_cache(maxsize=1)
def load_pois():
    """
    Load POIs from JSON and return a dictionary of DataFrames/Lists per category.
    Returns:
        dict: { 'verde': [features...], 'trasporti': [features...], ... }
    """
    if not os.path.exists(POI_JSON_PATH):
        print(f"POI file not found at {POI_JSON_PATH}")
        return {}

    print(f"Loading POIs from {POI_JSON_PATH}...")
    try:
        with open(POI_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading POI JSON: {e}")
        return {}

    elements = data.get("elements", [])
    categorized_pois = {cat: [] for cat in CATEGORIES}

    for el in elements:
        if el.get("type") != "node":  # Focus on nodes for now for simplicity
            continue

        tags = el.get("tags", {})
        if not tags:
            continue

        # Classify
        assigned = False
        for cat_name, cat_def in CATEGORIES.items():
            if assigned:
                break

            criteria = cat_def["tags"]
            for tag_key, tag_values in criteria.items():
                if tag_key in tags:
                    if tag_values is None:  # Match any value for this tag
                        categorized_pois[cat_name].append(el)
                        assigned = True
                        break
                    elif tags[tag_key] in tag_values:
                        categorized_pois[cat_name].append(el)
                        assigned = True
                        break

    # Stats
    for cat, items in categorized_pois.items():
        print(f"POI Category '{cat}': {len(items)} items")

    return categorized_pois


def get_poi_category_color(category):
    return CATEGORIES.get(category, {}).get("color", "#888888")
