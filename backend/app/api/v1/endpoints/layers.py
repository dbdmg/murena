"""
Layers endpoints for POIs and Zone OMI.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

router = APIRouter(prefix="/layers", tags=["layers"])

# Cache for loaded data
_pois_cache: Optional[List[Dict]] = None
_zone_omi_cache: Optional[Dict] = None

import logging

logger = logging.getLogger(__name__)

# Path resolution:
# layers.py -> endpoints -> v1 -> api -> app -> backend -> then into data/
DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "data"
    / "FOLDER_STATIC_ROME"
)

logger.info(f"Layers DATA_DIR resolved to: {DATA_DIR}")


def _load_pois() -> List[Dict]:
    """Load and cache POIs from pois.json"""
    global _pois_cache
    if _pois_cache is None:
        pois_path = DATA_DIR / "pois.json"
        logger.info(f"Loading POIs from: {pois_path}")
        if pois_path.exists():
            try:
                with open(pois_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    _pois_cache = data.get("elements", [])
                logger.info(f"Loaded {len(_pois_cache)} POIs")
            except Exception as e:
                logger.error(f"Error loading POIs: {e}")
                _pois_cache = []
        else:
            logger.error(f"POIs file not found at {pois_path}")
            _pois_cache = []
    return _pois_cache


def _load_zone_omi() -> Dict:
    """Load and cache Zone OMI GeoJSON"""
    global _zone_omi_cache
    if _zone_omi_cache is None:
        zone_path = DATA_DIR / "Zone_omi_torino.geojson"
        logger.info(f"Loading Zone OMI from: {zone_path}")
        if zone_path.exists():
            try:
                with open(zone_path, "r", encoding="utf-8") as f:
                    _zone_omi_cache = json.load(f)
                logger.info("Loaded Zone OMI GeoJSON")
            except Exception as e:
                logger.error(f"Error loading Zone OMI: {e}")
                _zone_omi_cache = {"type": "FeatureCollection", "features": []}
        else:
            logger.error(f"Zone OMI file not found at {zone_path}")
            _zone_omi_cache = {"type": "FeatureCollection", "features": []}
    return _zone_omi_cache


# POI category mappings - 6 main categories matching amenities_config.py
POI_CATEGORIES = {
    "sanità": {
        "tags": [
            ("healthcare", "*"),
            ("amenity", "pharmacy"),
            ("amenity", "dentist"),
            ("amenity", "veterinary"),
            ("amenity", "hospital"),
            ("amenity", "clinic"),
            ("amenity", "doctors"),
        ],
        "icon": "",
        "color": "#22c55e",
    },
    "mobilità": {
        "tags": [
            ("railway", "station"),
            ("railway", "subway_entrance"),
            ("railway", "tram_stop"),
            ("highway", "bus_stop"),
            ("amenity", "charging_station"),
            ("amenity", "car_sharing"),
            ("amenity", "taxi"),
            ("amenity", "parking"),
            ("amenity", "bicycle_parking"),
            ("amenity", "bicycle_rental"),
        ],
        "icon": "",
        "color": "#f97316",
    },
    "verde": {
        "tags": [
            ("leisure", "park"),
            ("leisure", "garden"),
            ("landuse", "grass"),
            ("natural", "wood"),
            ("landuse", "forest"),
            ("leisure", "playground"),
        ],
        "icon": "",
        "color": "#10b981",
    },
    "sport": {
        "tags": [
            ("leisure", "sports_centre"),
            ("leisure", "stadium"),
            ("leisure", "fitness_centre"),
            ("leisure", "swimming_pool"),
            ("leisure", "pitch"),
            ("sport", "*"),
        ],
        "icon": "",
        "color": "#3b82f6",
    },
    "commerciale": {
        "tags": [
            ("shop", "supermarket"),
            ("shop", "convenience"),
            ("shop", "mall"),
            ("shop", "department_store"),
            ("amenity", "marketplace"),
            ("shop", "bakery"),
            ("shop", "butcher"),
        ],
        "icon": "",
        "color": "#8b5cf6",
    },
    "educazione": {
        "tags": [
            ("amenity", "school"),
            ("amenity", "university"),
            ("amenity", "college"),
            ("amenity", "kindergarten"),
            ("amenity", "library"),
        ],
        "icon": "",
        "color": "#eab308",
    },
}


def _matches_category(poi: Dict, category: str) -> bool:
    """Check if POI matches a category"""
    if category not in POI_CATEGORIES:
        return False

    tags = poi.get("tags", {})
    category_defs = POI_CATEGORIES[category]["tags"]

    for tag_key, tag_value in category_defs:
        # Check if the tag key exists in the POI
        if tag_key not in tags:
            continue
            
        poi_value = tags[tag_key]
        
        # Wildcard match: any value for this key is acceptable
        if tag_value == "*":
            return True
            
        # Exact match
        if poi_value == tag_value:
            return True
            
    return False


def _deduplicate_pois(pois: List[Dict], threshold_km: float = 0.2) -> List[Dict]:
    """
    Group POIs that have similar names and are close to each other.
    Simple greedy clustering.
    """
    if not pois:
        return []

    unique_pois = []
    # Sort by importance/completeness? For now just keep order.

    # We use a simplified lat/lon distance (1 deg ~ 111km)
    # 0.001 deg ~ 111m.
    # Threshold 0.2km ~ 0.0018 deg lat.
    THRESHOLD_DEG = 0.0018

    for poi in pois:
        name = poi.get("name", "").lower().strip()
        # If no name, keep it (cannot group confidently without name)
        if not name:
            unique_pois.append(poi)
            continue

        is_duplicate = False
        for existing in unique_pois:
            existing_name = existing.get("name", "").lower().strip()

            # Check name similarity (exact match for now is enough for Metro stations like "Porta Nuova")
            if name == existing_name:
                # Check distance
                d_lat = abs(poi["lat"] - existing["lat"])
                d_lon = abs(poi["lon"] - existing["lon"])

                if d_lat < THRESHOLD_DEG and d_lon < THRESHOLD_DEG:
                    is_duplicate = True
                    break

        if not is_duplicate:
            unique_pois.append(poi)

    return unique_pois


@router.get("/pois")
async def get_pois(
    categories: str = Query(
        None, description="Pipe-separated list of categories (sanità|mobilità|verde|sport|commerciale|educazione)"
    ),
    min_lat: Optional[float] = Query(None, description="Minimum latitude"),
    max_lat: Optional[float] = Query(None, description="Maximum latitude"),
    min_lon: Optional[float] = Query(None, description="Minimum longitude"),
    max_lon: Optional[float] = Query(None, description="Maximum longitude"),
    limit: Optional[int] = Query(None, description="Optional maximum number of POIs to return"),
) -> Dict[str, Any]:
    """
    Get POIs filtered by category and bounding box.

    Categories: sanità, mobilità, verde, sport, commerciale, educazione
    """
    all_pois = _load_pois()

    # Parse and determine categories to collect
    if categories:
        categories_to_collect = [c.strip() for c in categories.split("|") if c.strip()]
    else:
        categories_to_collect = list(POI_CATEGORIES.keys())
    
    # Initialize collection structures - collect all POIs
    pois_by_category: Dict[str, List[Dict]] = {cat: [] for cat in categories_to_collect}

    for poi in all_pois:
        # Must have coordinates
        if "lat" not in poi or "lon" not in poi:
            continue

        lat, lon = poi["lat"], poi["lon"]

        # Bounding box filter
        if min_lat is not None and lat < min_lat:
            continue
        if max_lat is not None and lat > max_lat:
            continue
        if min_lon is not None and lon < min_lon:
            continue
        if max_lon is not None and lon > max_lon:
            continue

        # Category matching
        matched_category = None
        matched_icon = ""
        matched_color = "#6b7280"

        for cat in categories_to_collect:
            if _matches_category(poi, cat):
                matched_category = cat
                cat_info = POI_CATEGORIES[cat]
                matched_icon = cat_info["icon"]
                matched_color = cat_info["color"]
                break
        
        if not matched_category:
            continue

        # Build POI object
        tags = poi.get("tags", {})
        poi_obj = {
            "id": poi.get("id"),
            "lat": lat,
            "lon": lon,
            "name": tags.get("name", ""),
            "category": matched_category,
            "icon": matched_icon,
            "color": matched_color,
            "details": {
                "address": f"{tags.get('addr:street', '')} {tags.get('addr:housenumber', '')}".strip(),
                "city": tags.get("addr:city", ""),
                "website": tags.get("website", ""),
                "phone": tags.get("phone", ""),
                "opening_hours": tags.get("opening_hours", ""),
                "description": tags.get("description", ""),
                "operator": tags.get("operator", ""),
            },
        }
        
        pois_by_category[matched_category].append(poi_obj)

    # Apply deduplication and collect all POIs
    final_pois = []
    
    for cat_pois in pois_by_category.values():
        deduplicated = _deduplicate_pois(cat_pois)
        final_pois.extend(deduplicated)
    
    # Apply optional limit if specified
    if limit is not None and limit > 0:
        final_pois = final_pois[:limit]


    return {
        "count": len(final_pois),
        "categories": list(POI_CATEGORIES.keys()),
        "pois": final_pois,
    }


@router.get("/zone-omi")
async def get_zone_omi() -> Dict[str, Any]:
    """
    Get Zone OMI GeoJSON for Torino.
    """
    geojson = _load_zone_omi()

    # Add color property to each feature based on zone code
    features = geojson.get("features", [])
    zone_colors = {}
    color_palette = [
        "#f87171",
        "#fb923c",
        "#fbbf24",
        "#a3e635",
        "#34d399",
        "#22d3ee",
        "#60a5fa",
        "#a78bfa",
        "#f472b6",
        "#fb7185",
    ]

    for i, feature in enumerate(features):
        props = feature.get("properties", {})
        zone_code = props.get("CODZONA", "")

        if zone_code not in zone_colors:
            zone_colors[zone_code] = color_palette[
                len(zone_colors) % len(color_palette)
            ]

        props["fillColor"] = zone_colors[zone_code]
        props["strokeColor"] = zone_colors[zone_code]

    return geojson
