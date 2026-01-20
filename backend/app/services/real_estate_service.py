"""
Real Estate Service - Handles building data loading, filtering, and retrieval.

This service provides:
- Loading real estate data from parquet files
- Filtering by multiple criteria (surface area, energy class, city, etc.)
- Pagination support
- Individual building lookup by ID
- Dataset caching for performance
"""

import asyncio
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from app.core.config import settings
from app.data.loaders import load_and_merge_data
from app.models.requests import BuildingFilters
from app.models.responses import (
    APEScores,
    BuildingResponse,
    Coordinates,
    POIScores,
    SubProperty,
)
from app.utils.logger import logger


class RealEstateService:
    """Service for managing real estate building data."""

    def __init__(self):
        """Initialize the service with an empty dataset cache."""
        self._dataset_cache: Dict[str, pd.DataFrame] = {}

    async def get_buildings(
        self,
        filters: BuildingFilters,
        limit: int = 100,
        offset: int = 0,
        dataset_key: str = "full",
    ) -> Tuple[List[BuildingResponse], int]:
        """
        Get filtered and paginated buildings.

        Args:
            filters: BuildingFilters object with filter criteria
            limit: Maximum number of results to return
            offset: Number of results to skip
            dataset_key: Dataset to use ('full', 'meta', 'ape')

        Returns:
            Tuple of (list of buildings, total count before pagination)
        """
        # Load dataset (async wrapper for sync operation)
        df = await asyncio.to_thread(self._load_dataset, dataset_key)

        if df is None or df.empty:
            logger.warning(f"Dataset '{dataset_key}' is empty or failed to load")
            return [], 0

        # Apply filters
        filtered_df = self._apply_filters(df, filters)
        total_count = len(filtered_df)

        # Apply pagination
        paginated_df = filtered_df.iloc[offset : offset + limit]

        # Convert to response models
        buildings = []
        for _, row in paginated_df.iterrows():
            try:
                building = self._df_row_to_building(row)
                buildings.append(building)
            except Exception as e:
                logger.error(f"Error converting row to building: {e}")
                continue

        return buildings, total_count

    async def get_building_by_id(
        self, building_id: str, dataset_key: str = "full"
    ) -> Optional[BuildingResponse]:
        """
        Get a single building by ID.

        Args:
            building_id: Building ID to retrieve
            dataset_key: Dataset to search in

        Returns:
            BuildingResponse or None if not found
        """
        df = await asyncio.to_thread(self._load_dataset, dataset_key)

        if df is None or df.empty:
            return None

        # Filter by ID (ensure string comparison)
        building_df = df[df["id"].astype(str) == str(building_id)]

        if building_df.empty:
            return None

        # Convert first row to building
        try:
            return self._df_row_to_building(building_df.iloc[0])
        except Exception as e:
            logger.error(f"Error converting building {building_id}: {e}")
            return None

    def _str_to_bool(self, value) -> bool:
        """Convert string 'True'/'False' or bool to boolean."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)

    def _load_dataset(self, dataset_key: str) -> Optional[pd.DataFrame]:
        """
        Load dataset with caching.

        Args:
            dataset_key: Dataset identifier ('full', 'meta', 'ape')

        Returns:
            DataFrame or None if load fails
        """
        # Check cache first
        if dataset_key in self._dataset_cache:
            logger.info(f"Using cached dataset: {dataset_key}")
            return self._dataset_cache[dataset_key]

        # Get file path from settings
        file_path = self._get_dataset_path(dataset_key)

        if not file_path:
            logger.error(f"Unknown dataset key: {dataset_key}")
            return None

        # Load data using existing loader
        logger.info(f"Loading dataset: {dataset_key} from {file_path}")
        df = load_and_merge_data(file_path)

        if df is not None and not df.empty:
            # Cache the dataset
            self._dataset_cache[dataset_key] = df
            logger.info(f"Loaded and cached {len(df)} buildings from {dataset_key}")

        return df

    def _get_dataset_path(self, dataset_key: str) -> Optional[str]:
        """
        Get file path for dataset key.

        Args:
            dataset_key: Dataset identifier

        Returns:
            File path or None
        """
        dataset_paths = {
            "full": settings.DATASET_FULL,
            "meta": settings.DATASET_META,
            "ape": settings.APE_DETAILED_DATA_PATH,  # This one matches
        }
        return dataset_paths.get(dataset_key.lower())

    def _apply_filters(
        self, df: pd.DataFrame, filters: BuildingFilters
    ) -> pd.DataFrame:
        """
        Apply filters to DataFrame.

        Args:
            df: Input DataFrame
            filters: BuildingFilters object

        Returns:
            Filtered DataFrame
        """
        result = df.copy()

        # Filter by city
        if filters.city:
            if "city" in result.columns:
                result = result[result["city"].str.lower() == filters.city.lower()]
            elif "comune" in result.columns:
                result = result[result["comune"].str.lower() == filters.city.lower()]

        # Filter by surface area range
        if filters.min_surface is not None:
            if "surface_area" in result.columns:
                result = result[result["surface_area"] >= filters.min_surface]
            elif "superficie" in result.columns:
                result = result[result["superficie"] >= filters.min_surface]

        if filters.max_surface is not None:
            if "surface_area" in result.columns:
                result = result[result["surface_area"] <= filters.max_surface]
            elif "superficie" in result.columns:
                result = result[result["superficie"] <= filters.max_surface]

        # Filter by energy classes
        if filters.energy_classes:
            energy_col = None
            # Check for various possible column names
            for col_name in [
                "energy_class",
                "classe_energetica",
                "classe",
                "classe_energetica_ape",
            ]:
                if col_name in result.columns:
                    energy_col = col_name
                    break

            if energy_col:
                # Normalize filter classes to uppercase
                filter_classes = [c.upper() for c in filters.energy_classes]
                logger.info(
                    f"Filtering by energy classes: {filter_classes}, column: {energy_col}"
                )

                # Match either exact class (A, B, C) or class with number (A1, A2, A3, A4)
                def matches_class(val):
                    if pd.isna(val):
                        return False
                    val_upper = str(val).upper().strip()
                    for fc in filter_classes:
                        # Exact match or starts with (e.g., "A" matches "A", "A1", "A2")
                        if val_upper == fc or val_upper.startswith(fc):
                            return True
                    return False

                before_count = len(result)
                result = result[result[energy_col].apply(matches_class)]
                logger.info(f"Energy filter: {before_count} -> {len(result)} buildings")
            else:
                logger.warning(
                    f"Energy class column not found in columns: {result.columns.tolist()[:10]}"
                )

        # Filter by minimum score
        if filters.min_score is not None and "score" in result.columns:
            result = result[result["score"] >= filters.min_score]

        # Filter by maximum score
        if filters.max_score is not None and "score" in result.columns:
            result = result[result["score"] <= filters.max_score]

        # Filter by evaluation status
        if filters.is_evaluated is not None and "is_evaluated" in result.columns:
            result = result[result["is_evaluated"] == filters.is_evaluated]

        # Filter by epoche costruzione (string matching)
        if filters.epoche_costruzione:
            epoca_col = None
            if "epoca_costruzione" in result.columns:
                epoca_col = "epoca_costruzione"

            if epoca_col:
                logger.info(f"Filtering by epoche: {filters.epoche_costruzione}")
                before_count = len(result)
                result = result[result[epoca_col].isin(filters.epoche_costruzione)]
                logger.info(f"Epoca filter: {before_count} -> {len(result)} buildings")

        # Filter by property types
        if filters.property_types:
            type_col = None
            if "property_type" in result.columns:
                type_col = "property_type"
            elif "tipologia_edilizia_str" in result.columns:
                type_col = "tipologia_edilizia_str"

            if type_col:
                # Case-insensitive match
                lower_types = [t.lower() for t in filters.property_types]
                result = result[result[type_col].str.lower().isin(lower_types)]

        # Filter by utilizzo_bene (string matching)
        if filters.utilizzo_bene:
            utilizzo_col = None
            if "utilizzo_del_bene" in result.columns:
                utilizzo_col = "utilizzo_del_bene"
            elif "utilizzo" in result.columns:
                utilizzo_col = "utilizzo"

            if utilizzo_col:
                lower_vals = [v.lower() for v in filters.utilizzo_bene]
                result = result[result[utilizzo_col].str.lower().isin(lower_vals)]

        # Filter by vincolo_culturale (string matching)
        if filters.vincolo_culturale:
            vincolo_col = None
            if "vincolo_culturale_paesaggistico" in result.columns:
                vincolo_col = "vincolo_culturale_paesaggistico"
            elif "vincolo" in result.columns:
                vincolo_col = "vincolo"

            if vincolo_col:
                lower_vals = [v.lower() for v in filters.vincolo_culturale]
                result = result[result[vincolo_col].str.lower().isin(lower_vals)]

        # Filter by is_meta_immobile
        if filters.is_meta_immobile is not None:
            meta_col = None
            if "meta_building" in result.columns:
                meta_col = "meta_building"
            elif "meta_immobile" in result.columns:
                meta_col = "meta_immobile"
            elif "is_meta" in result.columns:
                meta_col = "is_meta"

            if meta_col:
                if filters.is_meta_immobile:
                    # Only meta buildings
                    result = result[result[meta_col] == True]
                else:
                    # Only non-meta buildings
                    result = result[
                        (result[meta_col] == False) | (result[meta_col].isna())
                    ]

        # Filter by natura_bene (FABBRICATO or TERRENO)
        if filters.natura_bene:
            natura_col = None
            if "natura_del_bene" in result.columns:
                natura_col = "natura_del_bene"
            elif "natura" in result.columns:
                natura_col = "natura"

            if natura_col:
                result = result[
                    result[natura_col].str.upper() == filters.natura_bene.upper()
                ]

        # TODO: Filter by run_id (requires database lookup for run results)
        if filters.run_id:
            logger.warning(f"run_id filter not yet implemented: {filters.run_id}")

        return result

    def _df_row_to_building(self, row: pd.Series) -> BuildingResponse:
        """
        Convert DataFrame row to BuildingResponse model.

        Args:
            row: Pandas Series (DataFrame row)

        Returns:
            BuildingResponse object
        """

        # Helper to safely get values
        def safe_get(key: str, default=None, alternatives: List[str] = None):
            """Try key, then alternatives, return default if not found."""
            if key in row.index and pd.notna(row[key]):
                return row[key]
            if alternatives:
                for alt in alternatives:
                    if alt in row.index and pd.notna(row[alt]):
                        return row[alt]
            return default

        # Extract coordinates
        lat = safe_get("lat", alternatives=["latitude", "coordinata_y", "latitudine"])
        lon = safe_get("lon", alternatives=["longitude", "coordinata_x", "longitudine"])

        if lat is None or lon is None:
            # Try to extract from other common column names
            lat = lat or safe_get("coordinata_y")
            lon = lon or safe_get("coordinata_x")

        # Coordinates are required
        if lat is None or lon is None:
            raise ValueError(
                f"Missing coordinates for building {row.get('id', 'unknown')}"
            )

        coordinates = Coordinates(lat=float(lat), lon=float(lon))

        # Extract APE scores if available (using actual column names from dataset)
        ape_scores = None
        ape_score_cols = {
            "total": ["ape_score_total"],
            "class_score": ["ape_score_classe"],
            "system_score": ["ape_score_impianto"],
            "envelope_score": ["ape_score_involucro"],
            "renewables_score": ["ape_score_rinnovabili"],
        }

        ape_data = {}
        for key, cols in ape_score_cols.items():
            value = safe_get(cols[0], alternatives=cols[1:] if len(cols) > 1 else [])
            if value is not None:
                if key == "total":
                    ape_data[key] = float(value)
                else:
                    ape_data[key] = int(value) if not pd.isna(value) else 0

        if ape_data and "total" in ape_data:
            ape_scores = APEScores(
                total=ape_data.get("total", 0.0),
                class_score=ape_data.get("class_score", 0),
                system_score=ape_data.get("system_score", 0),
                envelope_score=ape_data.get("envelope_score", 0),
                renewables_score=ape_data.get("renewables_score", 0),
            )

        # Extract POI scores if available (using actual column names from dataset)
        poi_scores = None
        poi_columns = {
            "health": ["sanita"],
            "mobility": ["mobilita"],
            "green": ["verde"],
            "education": ["educazione"],
            "shopping": ["commerciale"],
            "sport": ["sport"],
        }

        poi_data = {}
        for key, cols in poi_columns.items():
            value = safe_get(cols[0], alternatives=cols[1:] if len(cols) > 1 else [])
            if value is not None:
                poi_data[key] = float(value)

        if poi_data:
            poi_scores = POIScores(**poi_data)

        # Parse APE files list
        def parse_ape_list(val):
            """Parse APE file list from various formats."""
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            if isinstance(val, list):
                return [str(item) for item in val if item]
            if isinstance(val, str):
                if not val.strip() or val.lower() == "nan":
                    return None
                try:
                    import ast

                    parsed = ast.literal_eval(val)
                    if isinstance(parsed, list):
                        return [str(item) for item in parsed if item]
                except Exception:
                    # Might be comma-separated or just a single file
                    if "," in val:
                        return [v.strip() for v in val.split(",") if v.strip()]
                    return [val] if val.strip() else None
            return None

        ape_files = parse_ape_list(
            safe_get(
                "ape_files",
                alternatives=[
                    "list_file_ape_filtered",
                    "list_file_ape_filtered_parsed",
                ],
            )
        )

        # Parse sub-properties for meta immobili
        sub_properties = None
        if self._str_to_bool(safe_get("meta_immobile", default=False)):
            id_list_raw = safe_get("id_list")
            if id_list_raw is not None:
                try:
                    import ast

                    # Parse id_list which might be a string representation of a list
                    if isinstance(id_list_raw, str):
                        id_list_parsed = ast.literal_eval(id_list_raw)
                    elif isinstance(id_list_raw, list):
                        id_list_parsed = id_list_raw
                    else:
                        id_list_parsed = []

                    if id_list_parsed and len(id_list_parsed) > 0:
                        sub_properties = []
                        # Get the cached dataset to look up sub-properties
                        df = self._dataset_cache.get("full")
                        for sub_id in id_list_parsed[:20]:  # Limit to 20
                            sub_id_str = str(sub_id)
                            sub_prop = SubProperty(id=sub_id_str)

                            # Try to find details in the dataset
                            if df is not None:
                                sub_row = df[df["id"].astype(str) == sub_id_str]
                                if not sub_row.empty:
                                    sub_row = sub_row.iloc[0]
                                    if (
                                        "superficie_di_riferimento_mq" in sub_row.index
                                        and pd.notna(
                                            sub_row["superficie_di_riferimento_mq"]
                                        )
                                    ):
                                        sub_prop.surface_area = float(
                                            sub_row["superficie_di_riferimento_mq"]
                                        )
                                    if (
                                        "tipologia_bene_immobile" in sub_row.index
                                        and pd.notna(sub_row["tipologia_bene_immobile"])
                                    ):
                                        sub_prop.property_type = str(
                                            sub_row["tipologia_bene_immobile"]
                                        )

                            sub_properties.append(sub_prop)
                except Exception as e:
                    logger.warning(f"Error parsing sub-properties: {e}")
                    sub_properties = None

        # Build the response
        return BuildingResponse(
            id=str(safe_get("id", "")),
            address=safe_get("address", alternatives=["indirizzo", "via"]),
            city=safe_get("city", alternatives=["comune", "codice_comune"]),
            coordinates=coordinates,
            surface_area=safe_get(
                "surface_area", alternatives=["superficie_di_riferimento_mq"]
            ),
            construction_year=str(
                safe_get("construction_year", alternatives=["epoca_costruzione"])
            ),
            energy_class=safe_get(
                "energy_class", alternatives=["classe_energetica_ape"]
            ),
            score=safe_get("score", alternatives=["ape_score_total"]),
            rooms=None,  # Not present in provided columns
            bathrooms=None,  # Not present in provided columns
            floor=None,  # Not present in provided columns
            price=safe_get("price", alternatives=["canone_annuale"]),
            description=safe_get(
                "description", alternatives=["utilizzo_del_bene", "natura_del_bene"]
            ),
            # Extended property info
            property_type=safe_get(
                "property_type", alternatives=["tipologia_bene_immobile"]
            ),
            legal_nature=safe_get(
                "legal_nature", alternatives=["natura_giuridica_del_bene"]
            ),
            cultural_constraint=safe_get(
                "cultural_constraint", alternatives=["vincolo_culturale_paesaggistico"]
            ),
            purpose=safe_get("purpose", alternatives=["finalita"]),
            omi_zone=safe_get("omi_zone", alternatives=["zona_omi"]),
            cadastral_sheet=str(safe_get("cadastral_sheet", alternatives=["foglio"])),
            cadastral_parcel=str(
                safe_get("cadastral_parcel", alternatives=["particella"])
            ),
            is_evaluated=bool(safe_get("is_evaluated", default=False)),
            meta_building=self._str_to_bool(safe_get("meta_immobile", default=False)),
            # Map new requested fields explicitly
            meta_immobile=self._str_to_bool(safe_get("meta_immobile", default=False)),
            canone_annuale=safe_get("canone_annuale", default=None),
            tipo_detenzione_a_terzi=safe_get("tipo_detenzione_a_terzi", default=None),
            data_decorrenza=safe_get("data_decorrenza", default=None),
            numero_immobili_per_catasto=safe_get(
                "numero_immobili_per_catasto", default=None
            ),
            id_list=(
                str(safe_get("id_list", default="")) if safe_get("id_list") else None
            ),
            sub_properties=sub_properties,
            ape_scores=ape_scores,
            poi_scores=poi_scores,
            ape_files=ape_files,
            distance_km=None,
            poi_reference=None,
        )
