"""
Map endpoints for configuration, markers, and overlays.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException

from app.api import deps
from app.services.map_service import MapService

router = APIRouter()


@router.get("/config")
async def get_map_config(
    current_user: Any = Depends(deps.get_current_user_optional),
) -> Dict[str, Any]:
    """
    Get initial map configuration (center, zoom, style).
    """
    service = MapService()
    return await service.get_config()


@router.get("/overlays/{overlay_type}")
async def get_map_overlay(
    overlay_type: str,
    current_user: Any = Depends(deps.get_current_user_optional),
) -> Dict[str, Any]:
    """
    Get GeoJSON overlay data.

    Args:
        overlay_type: 'municipi', 'omi', or 'urbanistiche'
    """
    service = MapService()
    data = await service.get_overlay(overlay_type)

    if not data:
        raise HTTPException(status_code=404, detail=f"Overlay {overlay_type} not found")

    return data


@router.get("/markers")
async def get_map_markers(
    limit: int = 1000,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    city: Optional[str] = None,
    energy_classes: Optional[str] = None,  # Comma-separated: "A1,A2,B"
    min_surface: Optional[float] = None,
    max_surface: Optional[float] = None,
    epoche_costruzione: Optional[str] = None,  # Pipe-separated: "Prima del 1919|Dal 1919 al 1945"
    property_types: Optional[str] = None,  # Pipe-separated
    utilizzo_bene: Optional[str] = None,  # Pipe-separated
    vincolo_culturale: Optional[str] = None,  # Pipe-separated
    is_meta_immobile: Optional[bool] = None,
    natura_bene: Optional[str] = None,  # FABBRICATO or TERRENO
    current_user: Any = Depends(deps.get_current_user_optional),
) -> List[Dict[str, Any]]:
    """
    Get map markers for real estate properties with filtering.

    Query Params:
        limit: Max number of markers
        min_score/max_score: Score range filter
        city: Filter by city name
        energy_classes: Comma-separated energy classes (A1,A2,A4,B,C,D,E,F,G)
        min_surface/max_surface: Surface area range in m²
        epoche_costruzione: Pipe-separated construction periods
        property_types: Pipe-separated property types
        utilizzo_bene: Pipe-separated utilization statuses
        vincolo_culturale: Pipe-separated cultural constraints
        is_meta_immobile: Boolean for meta immobile filter
        natura_bene: FABBRICATO or TERRENO
    """
    service = MapService()
    filters = {}

    if min_score is not None:
        filters["min_score"] = min_score
    if max_score is not None:
        filters["max_score"] = max_score
    if city is not None:
        filters["city"] = city
    if energy_classes:
        filters["energy_classes"] = [c.strip().upper() for c in energy_classes.split(",")]
    if min_surface is not None:
        filters["min_surface"] = min_surface
    if max_surface is not None:
        filters["max_surface"] = max_surface
    if epoche_costruzione:
        filters["epoche_costruzione"] = [e.strip() for e in epoche_costruzione.split("|")]
    if property_types:
        filters["property_types"] = [t.strip() for t in property_types.split("|")]
    if utilizzo_bene:
        filters["utilizzo_bene"] = [u.strip() for u in utilizzo_bene.split("|")]
    if vincolo_culturale:
        filters["vincolo_culturale"] = [v.strip() for v in vincolo_culturale.split("|")]
    if is_meta_immobile is not None:
        filters["is_meta_immobile"] = is_meta_immobile
    if natura_bene:
        filters["natura_bene"] = natura_bene

    return await service.get_markers(limit=limit, filters=filters)
