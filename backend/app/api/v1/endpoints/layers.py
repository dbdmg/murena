"""Map layer endpoints for OSM points of interest."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import deps
from app.core.config import settings

router = APIRouter()

POI_PRESENTATION = {
    "healthcare": ("🏥", "#ef4444"),
    "mobility": ("🚇", "#3b82f6"),
    "green": ("🌳", "#22c55e"),
    "sport": ("⚽", "#f97316"),
    "commercial": ("🛒", "#eab308"),
    "education": ("🎓", "#a855f7"),
}


@lru_cache(maxsize=1)
def _load_pois_by_category() -> Dict[str, Any]:
    backend_dir = Path(__file__).resolve().parents[4]
    path = Path(settings.META_DIR) / "pois_by_category.json"
    if not path.is_absolute():
        path = backend_dir / path

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="POI dataset is unavailable") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="POI dataset could not be loaded") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=503, detail="POI dataset has an invalid format")
    return data


@router.get("/pois")
async def get_pois(
    categories: Optional[str] = Query(
        default=None, description="Pipe-separated POI categories"
    ),
    min_lat: Optional[float] = None,
    max_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lon: Optional[float] = None,
    limit: int = Query(default=10000, ge=1, le=25000),
    current_user: Any = Depends(deps.get_current_user_optional),
) -> Dict[str, Any]:
    """Return categorized POIs, optionally restricted to a map viewport."""
    del current_user  # The layer is public, like the other map overlays.

    bounds = (min_lat, max_lat, min_lon, max_lon)
    if any(value is not None for value in bounds) and not all(
        value is not None for value in bounds
    ):
        raise HTTPException(
            status_code=422, detail="All four viewport bounds must be provided"
        )

    requested = [
        item.strip().lower()
        for item in (categories or "").split("|")
        if item.strip()
    ]
    available = _load_pois_by_category()
    selected_categories = requested or list(POI_PRESENTATION)
    unknown = [
        category
        for category in selected_categories
        if category not in POI_PRESENTATION
    ]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unsupported POI categories: {', '.join(unknown)}")

    has_bounds = all(value is not None for value in bounds)
    pois = []
    for category in selected_categories:
        category_data = available.get(category, {})
        if not isinstance(category_data, dict):
            continue
        icon, color = POI_PRESENTATION[category]
        for amenity_type, entries in category_data.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                lat, lon = entry.get("lat"), entry.get("lon")
                if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                    continue
                if has_bounds:
                    assert min_lat is not None
                    assert max_lat is not None
                    assert min_lon is not None
                    assert max_lon is not None
                    if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                        continue
                pois.append({
                    "id": entry.get("id", f"{category}:{amenity_type}:{lat}:{lon}"),
                    "lat": lat,
                    "lon": lon,
                    "name": str(amenity_type).replace("_", " ").title(),
                    "category": category,
                    "icon": icon,
                    "color": color,
                })
                if len(pois) >= limit:
                    break
            if len(pois) >= limit:
                break
        if len(pois) >= limit:
            break

    return {"count": len(pois), "categories": selected_categories, "pois": pois}
