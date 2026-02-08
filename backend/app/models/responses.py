"""
Pydantic models for API responses.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class AnalysisResponse(BaseModel):
    """Response model for analysis request."""

    run_id: str
    status: str = Field(..., description="Status: 'processing', 'completed', 'failed'")
    message: str
    created_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "abc123def456",
                "status": "processing",
                "message": "Analysis started successfully",
                "created_at": "2026-01-15T22:00:00Z",
            }
        }
    )


class Coordinates(BaseModel):
    """Geographic coordinates."""

    lat: float
    lon: float


class APEScores(BaseModel):
    """APE (Energy Performance Certificate) scores."""

    total: float
    class_score: int
    system_score: int
    envelope_score: int
    renewables_score: int


class POIScores(BaseModel):
    """Points of Interest scores."""

    health: Optional[float] = None
    mobility: Optional[float] = None
    green: Optional[float] = None
    education: Optional[float] = None
    shopping: Optional[float] = None
    sport: Optional[float] = None


class SubProperty(BaseModel):
    """Sub-property info for meta immobili."""

    id: str
    surface_area: Optional[float] = None
    property_type: Optional[str] = None


class BuildingResponse(BaseModel):
    """Response model for a single building."""

    id: str
    address: Optional[str] = None
    city: Optional[str] = None
    coordinates: Coordinates
    surface_area: Optional[float] = None
    construction_year: Optional[str] = None
    energy_class: Optional[str] = None
    score: Optional[float] = None
    rooms: Optional[float] = None
    bathrooms: Optional[float] = None
    floor: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    # Extended property info
    property_type: Optional[str] = None  # tipologia_bene_immobile
    legal_nature: Optional[str] = None  # natura_giuridica_del_bene
    cultural_constraint: Optional[str] = None  # vincolo_culturale_paesaggistico
    purpose: Optional[str] = None  # finalita
    omi_zone: Optional[str] = None  # zona_omi
    cadastral_sheet: Optional[str] = None  # foglio
    cadastral_parcel: Optional[str] = None  # particella
    is_evaluated: bool = False
    meta_building: bool = False
    # Extra fields requested by user
    meta_immobile: Optional[bool] = None
    canone_annuale: Optional[float] = None
    tipo_detenzione_a_terzi: Optional[str] = None
    data_decorrenza: Optional[str] = None
    numero_immobili_per_catasto: Optional[int] = None
    id_list: Optional[str] = None
    sub_properties: Optional[List[SubProperty]] = (
        None  # Detailed sub-properties for meta immobili
    )
    ape_scores: Optional[APEScores] = None
    poi_scores: Optional[POIScores] = None
    ape_files: Optional[List[str]] = None  # List of APE file paths/identifiers
    distance_km: Optional[float] = None
    poi_reference: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BuildingsListResponse(BaseModel):
    """Response model for buildings list."""

    buildings: List[BuildingResponse]
    total: int
    limit: int
    offset: int
    has_more: bool = Field(..., description="Whether more results are available")


class AnalysisResults(BaseModel):
    """Complete analysis results."""

    run_id: str
    query: str
    status: str
    buildings: List[BuildingResponse]
    location: Optional[List[List[Any]]] = None  # [[name, lat, lon], ...]
    filters_applied: Optional[Dict[str, Any]] = None
    gemini_responses: Optional[Dict[str, Any]] = None
    broker_summary: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class StepState(BaseModel):
    """State of a single analysis step."""

    label: str
    state: str  # "pending", "current", "done"
    detail: Optional[str] = None


class ProgressUpdate(BaseModel):
    """Progress update via WebSocket."""

    type: str = "progress"
    progress: int = Field(..., ge=0, le=100)
    step: str
    detail: str
    steps_state: Optional[List[StepState]] = None


class AnalysisComplete(BaseModel):
    """Analysis completion message via WebSocket."""

    type: str = "complete"
    results: AnalysisResults


class AgentStep(BaseModel):
    """Normalized view of a single agent step (prompt + response + extra data)."""

    key: str
    label: Optional[str] = None
    prompt: Optional[Dict[str, Any]] = None
    response: Optional[Any] = None
    data: Optional[Dict[str, Any]] = None


class AgentStepsResponse(BaseModel):
    """Normalized view of gemini_responses for a run, suitable for UI inspection."""

    run_id: str
    steps: List[AgentStep]


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User profile response."""

    id: int
    username: str
    email: Optional[str] = None
    created_at: datetime


class AppFeedbackResponse(BaseModel):
    """Response model for app-level feedback entries."""

    id: int
    run_id: str
    rating: Optional[int] = None
    comment: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime
