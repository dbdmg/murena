"""
Service for map-related operations, including GeoJSON handling and marker generation.
"""

import json
import os
from typing import Dict, Any, List, Optional
import logging

from app.core.config import settings
from app.models.responses import BuildingResponse, Coordinates
from app.services.real_estate_service import RealEstateService

logger = logging.getLogger(__name__)


class MapService:
    """Service for managing map data and overlays."""

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self.real_estate_service = RealEstateService()

    def _load_geojson(self, path: str) -> Optional[Dict[str, Any]]:
        """Load GeoJSON from file with caching."""
        if path in self._cache:
            return self._cache[path]

        try:
            # Resolve relative path from backend directory
            # settings paths are relative to backend/
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            # actually settings paths like "../FOLDER..." are relative to where the app runs?
            # Config says: "File Paths (relative to backend/ directory)"
            # So if running from backend/, "../FOLDER" is correct.

            full_path = os.path.join(base_dir, path)
            # Normalize path
            full_path = os.path.normpath(full_path)

            if not os.path.exists(full_path):
                # Try relative to CWD if failed
                full_path = os.path.abspath(path)

            if not os.path.exists(full_path):
                logger.error(f"GeoJSON file not found: {full_path}")
                return None

            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._cache[path] = data
                return data
        except Exception as e:
            logger.error(f"Error loading GeoJSON {path}: {e}")
            return None

    async def get_overlay(self, overlay_type: str) -> Optional[Dict[str, Any]]:
        """
        Get GeoJSON overlay by type.

        Args:
            overlay_type: 'municipi', 'omi', or 'urbanistiche'
        """
        if overlay_type == "municipi":
            return self._load_geojson(settings.MUNICIPI_GEOJSON)
        elif overlay_type == "omi":
            return self._load_geojson(settings.ZONE_OMI_GEOJSON)
        elif overlay_type == "urbanistiche":
            return self._load_geojson(settings.ZONE_URBANISTICHE_GEOJSON)
        else:
            return None

    async def get_markers(
        self, limit: int = 1000, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get map markers from real estate data.

        Returns simplified objects for map display.
        """
        # Get buildings from RealEstateService
        # We need to construct filters object if provided
        from app.models.requests import BuildingFilters

        build_filters = BuildingFilters(**(filters or {}))
        logger.info(f"get_markers called with limit={limit}, filters={filters}")

        # Override limit for map optimization
        buildings, total_count = await self.real_estate_service.get_buildings(
            filters=build_filters, limit=limit, offset=0
        )

        logger.info(
            f"get_buildings returned {len(buildings)} buildings, total_count={total_count}"
        )

        markers = []
        for b in buildings:
            if b.coordinates:
                markers.append(
                    {
                        "id": b.id,
                        "lat": b.coordinates.lat,
                        "lng": b.coordinates.lon,
                        # Full data from dataset
                        "address": b.address,
                        "city": b.city,
                        "surface_area": b.surface_area,
                        "construction_year": b.construction_year,
                        "energy_class": b.energy_class,
                        "score": b.score,
                        "price": b.price,
                        "description": b.description,
                        "rooms": b.rooms,
                        "bathrooms": b.bathrooms,
                        "floor": b.floor,
                        "is_evaluated": b.is_evaluated,
                        "meta_building": b.meta_building,
                        # New metadata fields
                        "meta_immobile": b.meta_immobile,
                        "canone_annuale": b.canone_annuale,
                        "tipo_detenzione_a_terzi": b.tipo_detenzione_a_terzi,
                        "data_decorrenza": b.data_decorrenza,
                        "numero_immobili_per_catasto": b.numero_immobili_per_catasto,
                        "id_list": b.id_list,
                        # Extended property info
                        "property_type": b.property_type,
                        "legal_nature": b.legal_nature,
                        "cultural_constraint": b.cultural_constraint,
                        "purpose": b.purpose,
                        "omi_zone": b.omi_zone,
                        "cadastral_sheet": b.cadastral_sheet,
                        "cadastral_parcel": b.cadastral_parcel,
                        # APE scores if available
                        "ape_scores": (
                            {
                                "total": b.ape_scores.total if b.ape_scores else None,
                                "class_score": (
                                    b.ape_scores.class_score if b.ape_scores else None
                                ),
                                "system_score": (
                                    b.ape_scores.system_score if b.ape_scores else None
                                ),
                                "envelope_score": (
                                    b.ape_scores.envelope_score
                                    if b.ape_scores
                                    else None
                                ),
                                "renewables_score": (
                                    b.ape_scores.renewables_score
                                    if b.ape_scores
                                    else None
                                ),
                            }
                            if b.ape_scores
                            else None
                        ),
                        # POI scores if available
                        "poi_scores": (
                            {
                                "health": b.poi_scores.health if b.poi_scores else None,
                                "mobility": (
                                    b.poi_scores.mobility if b.poi_scores else None
                                ),
                                "green": b.poi_scores.green if b.poi_scores else None,
                                "education": (
                                    b.poi_scores.education if b.poi_scores else None
                                ),
                                "shopping": (
                                    b.poi_scores.shopping if b.poi_scores else None
                                ),
                                "sport": b.poi_scores.sport if b.poi_scores else None,
                            }
                            if b.poi_scores
                            else None
                        ),
                        # APE files list
                        "ape_files": b.ape_files,
                        # Sub-properties for meta immobili
                        "sub_properties": (
                            [
                                {
                                    "id": sp.id,
                                    "surface_area": sp.surface_area,
                                    "property_type": sp.property_type,
                                }
                                for sp in b.sub_properties
                            ]
                            if b.sub_properties
                            else None
                        ),
                    }
                )

        return markers

    async def get_config(self) -> Dict[str, Any]:
        """Get default map configuration."""
        return {
            "center": {
                "lat": settings.DEFAULT_MAP_CENTER_LAT,
                "lng": settings.DEFAULT_MAP_CENTER_LON,
            },
            "zoom": settings.DEFAULT_MAP_ZOOM,
            "style": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",  # Default OSM
            "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }
