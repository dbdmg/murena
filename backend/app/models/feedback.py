"""
Pydantic models for agent feedback.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class FeedbackCreate(BaseModel):
    """Request model for creating feedback."""

    run_id: str = Field(..., description="Analysis run ID")
    agent_name: Optional[str] = Field(
        None, description="Agent name (null for global feedback)"
    )
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    comment: Optional[str] = Field(None, description="Optional text comment")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "a6cb9dd3-04e9-4219-b298-afa4121330c1",
                "agent_name": "ranking-agent",
                "rating": 5,
                "comment": "Ottima analisi, risultati molto precisi",
            }
        }
    )


class FeedbackResponse(BaseModel):
    """Response model for feedback."""

    id: int
    run_id: str
    agent_name: Optional[str] = None
    building_id: Optional[str] = None
    rating: int
    comment: Optional[str] = None
    created_at: datetime
    user_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class FeedbackListResponse(BaseModel):
    """Response model for list of feedback entries."""

    feedbacks: list[FeedbackResponse]
    total: int
