"""
Pydantic models for API requests.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List


class AnalysisRequest(BaseModel):
    """Request model for starting a new analysis."""

    query: str = Field(..., description="Natural language query for property search")
    dataset_key: str = Field(
        default="full", description="Dataset to use: 'full', 'meta', or 'ape'"
    )
    map_limit: int = Field(
        default=1000,
        ge=1,
        le=5000,
        description="Maximum number of results to show on map",
    )
    llm_limit: int = Field(
        default=10,
        ge=1,
        le=10,
        description="Maximum number of properties to evaluate with LLM (local cap: 10)",
    )
    analysis_mode: str = Field(
        default="agent", description="Analysis mode: 'classic' or 'agent'"
    )
    use_relaxation: bool = Field(
        default=True, description="Whether to use query relaxation if 0 results found"
    )
    model_type: Optional[str] = Field(
        default=None, description="LLM model type to use (e.g. 'vllm-gemma3-27b', 'vllm-qwen')"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Apartments in Turin near the Polytechnic with energy class A",
                "dataset_key": "full",
                "map_limit": 500,
                "llm_limit": 10,
                "analysis_mode": "agent",
            }
        }
    )


class LoginRequest(BaseModel):
    """Request model for user login."""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """Request model for user registration."""

    username: str
    password: str
    email: Optional[str] = None


class FeedbackRequest(BaseModel):
    """Request model for submitting feedback on a building."""

    building_id: str
    run_id: str
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = None
    helpful: Optional[bool] = None


class AppFeedbackRequest(BaseModel):
    """Request model for app-level feedback (not tied to a specific building)."""

    run_id: str = Field(..., description="Analysis run ID this feedback refers to")
    payload: dict = Field(
        default_factory=dict,
        description="Arbitrary structured feedback payload (will be stored as JSON string)",
    )
    rating: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Optional overall rating for the app/session (1-5)",
    )
    comment: Optional[str] = Field(None, description="Optional free-text comment")


class BuildingFilters(BaseModel):
    """Filter parameters for buildings list endpoint."""

    run_id: Optional[str] = Field(None, description="Filter by analysis run ID")
    min_surface: Optional[float] = Field(
        None, ge=0, description="Minimum surface area in m²"
    )
    max_surface: Optional[float] = Field(
        None, ge=0, description="Maximum surface area in m²"
    )
    min_score: Optional[float] = Field(
        None, ge=0, le=100, description="Minimum evaluation score"
    )
    max_score: Optional[float] = Field(
        None, ge=0, le=100, description="Maximum evaluation score"
    )
    energy_classes: Optional[List[str]] = Field(
        None, description="List of energy classes (A1, A2, A4, B, C, D, E, F, G)"
    )
    city: Optional[str] = Field(None, description="Filter by city name")
    is_evaluated: Optional[bool] = Field(
        None, description="Filter by evaluation status"
    )
    construction_periods: Optional[List[str]] = Field(
        None,
        description="List of construction periods (e.g. 'Before 1919', 'From 1919 to 1945')",
    )
    property_types: Optional[List[str]] = Field(
        None, description="List of property types to include"
    )
    asset_utilization: Optional[List[str]] = Field(
        None,
        description="List of asset utilization statuses (Directly used, Not used, etc.)",
    )
    cultural_constraints: Optional[List[str]] = Field(
        None, description="List of cultural constraint types"
    )
    is_meta_building: Optional[bool] = Field(
        None, description="Filter by meta building status (True = meta buildings only)"
    )
    asset_nature: Optional[str] = Field(
        None, description="Filter by asset nature (BUILDING or LAND)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "city": "Rome",
                "min_surface": 50,
                "max_surface": 150,
                "energy_classes": ["A1", "B"],
                "min_score": 70,
                "construction_periods": ["From 1991 to 2000", "After 2010"],
            }
        }
    )
