"""
Buildings API endpoints.

Provides REST API for querying and retrieving building data:
- GET /buildings - List buildings with filtering and pagination
- GET /buildings/{building_id} - Get single building details
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.requests import BuildingFilters
from app.models.responses import BuildingResponse, BuildingsListResponse
from app.services.real_estate_service import RealEstateService
from app.utils.logger import logger

router = APIRouter()

# Initialize service (singleton pattern)
real_estate_service = RealEstateService()


@router.get("/buildings", response_model=BuildingsListResponse)
async def list_buildings(
    run_id: Optional[str] = Query(None, description="Filter by analysis run ID"),
    min_surface: Optional[float] = Query(
        None, ge=0, description="Minimum surface area in m²"
    ),
    max_surface: Optional[float] = Query(
        None, ge=0, description="Maximum surface area in m²"
    ),
    min_score: Optional[float] = Query(
        None, ge=0, le=100, description="Minimum evaluation score"
    ),
    energy_classes: Optional[List[str]] = Query(
        None, description="Energy classes (e.g., A, B, C)"
    ),
    city: Optional[str] = Query(None, description="Filter by city name"),
    is_evaluated: Optional[bool] = Query(
        None, description="Show only evaluated buildings"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    dataset_key: str = Query(
        "full", description="Dataset to use: 'full', 'meta', or 'ape'"
    ),
    db: Session = Depends(get_db),
):
    """
    List buildings with optional filtering and pagination.

    ## Filters

    - **run_id**: Filter by analysis run ID (returns only buildings from that analysis)
    - **min_surface**: Minimum surface area in square meters
    - **max_surface**: Maximum surface area in square meters
    - **min_score**: Minimum evaluation score (0-100)
    - **energy_classes**: List of energy classes to include (e.g., ["A", "B"])
    - **city**: Filter by city name (case-insensitive)
    - **is_evaluated**: Show only buildings that have been evaluated by LLM

    ## Pagination

    - **limit**: Maximum number of results to return (1-1000, default: 100)
    - **offset**: Number of results to skip (default: 0)
    - **dataset_key**: Which dataset to query (default: "full")

    ## Response

    Returns a paginated list of buildings with:
    - Total count of matching buildings
    - Current page parameters (limit, offset)
    - Whether more results are available (has_more)
    - List of building objects

    ## Example

    ```
    GET /api/v1/buildings?city=Roma&min_surface=50&max_surface=150&limit=20
    ```
    """
    try:
        # Build filters object
        filters = BuildingFilters(
            run_id=run_id,
            min_surface=min_surface,
            max_surface=max_surface,
            min_score=min_score,
            energy_classes=energy_classes,
            city=city,
            is_evaluated=is_evaluated,
        )

        # Get buildings from service
        buildings, total = await real_estate_service.get_buildings(
            filters=filters, limit=limit, offset=offset, dataset_key=dataset_key, db=db
        )

        # Calculate if more results are available
        has_more = (offset + len(buildings)) < total

        logger.info(
            f"Buildings query: {len(buildings)} results "
            f"(total: {total}, offset: {offset}, limit: {limit})"
        )

        return BuildingsListResponse(
            buildings=buildings,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    except Exception as e:
        logger.error(f"Error in list_buildings: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve buildings: {str(e)}"
        )


@router.get("/buildings/{building_id}", response_model=BuildingResponse)
async def get_building(
    building_id: str,
    dataset_key: str = Query(
        "full", description="Dataset to search: 'full', 'meta', or 'ape'"
    ),
):
    """
    Get detailed information for a specific building by ID.

    ## Parameters

    - **building_id**: Unique identifier of the building (path parameter)
    - **dataset_key**: Which dataset to search (query parameter, default: "full")

    ## Response

    Returns a single building object with all available information including:
    - Basic info (address, city, surface area, etc.)
    - Coordinates (latitude, longitude)
    - Energy class and APE scores (if available)
    - POI scores (health, mobility, green spaces, etc.)
    - Evaluation score and status (if evaluated)

    ## Errors

    - **404**: Building not found in the specified dataset
    - **500**: Server error during retrieval

    ## Example

    ```
    GET /api/v1/buildings/12345
    ```
    """
    try:
        building = await real_estate_service.get_building_by_id(
            building_id=building_id, dataset_key=dataset_key
        )

        if not building:
            raise HTTPException(
                status_code=404,
                detail=f"Building with ID '{building_id}' not found in dataset '{dataset_key}'",
            )

        logger.info(f"Retrieved building: {building_id} from dataset: {dataset_key}")
        return building

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error retrieving building {building_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve building: {str(e)}"
        )
