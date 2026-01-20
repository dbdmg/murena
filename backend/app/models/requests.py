"""
Pydantic models for API requests.
"""

from pydantic import BaseModel, Field
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
        default=25,
        ge=1,
        le=50,
        description="Maximum number of properties to evaluate with LLM",
    )
    analysis_mode: str = Field(
        default="agent", description="Analysis mode: 'classic' or 'agent'"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Appartamenti a Torino vicino al Politecnico con classe energetica A",
                "dataset_key": "full",
                "map_limit": 500,
                "llm_limit": 10,
                "analysis_mode": "agent",
            }
        }


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
    epoche_costruzione: Optional[List[str]] = Field(
        None,
        description="List of construction periods (e.g. 'Prima del 1919', 'Dal 1919 al 1945')",
    )
    property_types: Optional[List[str]] = Field(
        None, description="List of property types to include"
    )
    utilizzo_bene: Optional[List[str]] = Field(
        None,
        description="List of asset utilization statuses (Utilizzato direttamente, Non utilizzato, etc.)",
    )
    vincolo_culturale: Optional[List[str]] = Field(
        None, description="List of cultural constraint types"
    )
    is_meta_immobile: Optional[bool] = Field(
        None, description="Filter by meta immobile status (True = meta immobili only)"
    )
    natura_bene: Optional[str] = Field(
        None, description="Filter by asset nature (FABBRICATO or TERRENO)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "city": "Roma",
                "min_surface": 50,
                "max_surface": 150,
                "energy_classes": ["A1", "B"],
                "min_score": 70,
                "epoche_costruzione": ["Dal 1991 al 2000", "Dopo il 2010"],
            }
        }
