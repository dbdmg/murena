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


class EnergyScores(BaseModel):
    """Energy Performance Certificate (EPC) scores."""

    total: float
    class_score: int
    system_score: int
    envelope_score: int
    renewables_score: int


class ProximityScores(BaseModel):
    """Proximity to Points of Interest scores."""

    healthcare: Optional[float] = None
    mobility: Optional[float] = None
    greenery: Optional[float] = None
    education: Optional[float] = None
    commerce: Optional[float] = None
    sport: Optional[float] = None


class SubProperty(BaseModel):
    """Sub-property info for meta immobili."""

    id: str
    surface_area: Optional[float] = None
    property_type: Optional[str] = None


class MapMarkerLite(BaseModel):
    """Lightweight marker data for initial map load."""

    id: str
    lat: float
    lng: float
    tier: int = 1
    # Filter fields (optional to keep payload small, but needed for client-side filtering)
    price: Optional[float] = None
    surface: Optional[float] = None
    energy_class: Optional[str] = None
    year: Optional[str] = None  # construction_year
    type: Optional[str] = None  # property_type
    usage: Optional[str] = None  # description/usage
    is_meta: bool = False
    
    model_config = ConfigDict(from_attributes=True)


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
    property_type: Optional[str] = None
    legal_nature: Optional[str] = None
    cultural_constraint: Optional[str] = None
    purpose: Optional[str] = None
    omi_zone: Optional[str] = None
    cadastral_sheet: Optional[str] = None
    cadastral_parcel: Optional[str] = None
    is_evaluated: bool = False
    is_match: bool = True
    meta_building: bool = False
    annual_rent: Optional[float] = None
    third_party_tenure_type: Optional[str] = None
    effective_date: Optional[str] = None
    cadastral_units_count: Optional[int] = None
    id_list: Optional[str] = None
    sub_properties: Optional[List[SubProperty]] = None
    energy_scores: Optional[EnergyScores] = None
    proximity_scores: Optional[ProximityScores] = None
    energy_files: Optional[List[str]] = None
    distance_km: Optional[float] = None
    proximity_reference: Optional[str] = None
    energy_performance_index: Optional[float] = None
    energy_score: Optional[float] = None
    greenery: Optional[float] = None
    mobility: Optional[float] = None
    education: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class BuildingsListResponse(BaseModel):
    """Response model for buildings list."""

    buildings: List[BuildingResponse]
    total: int
    limit: int
    offset: int
    has_more: bool = Field(..., description="Whether more results are available")


class AnalysisHistoryItem(BaseModel):
    """Lightweight summary of an analysis run for history lists."""

    run_id: str
    query: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    buildings_count: int = 0
    analysis_mode: str = "agent"  # Default to agent for backward compatibility


class AnalysisResults(BaseModel):
    """Complete analysis results."""

    run_id: str
    query: str
    status: str
    buildings: List[BuildingResponse]
    location: Optional[List[List[Any]]] = None  # [[name, lat, lon], ...]
    filters_applied: Optional[Dict[str, Any]] = None
    gemini_responses: Optional[Dict[str, Any]] = None
    results_count: int = 0
    broker_summary: Optional[str] = None
    agent_trace: Optional[List[Dict[str, Any]]] = None
    context: Optional[Dict[str, Any]] = None
    html_log: Optional[str] = None
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
