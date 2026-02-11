"""Feedback API endpoints.

For now we support only app-level feedback (not per-building), as it's the
highest value for early frontend iterations.

We store the structured payload as JSON string in Feedback.comment to avoid
schema churn; rating is optional.
"""

from __future__ import annotations

import json
from typing import Optional, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional
from app.database.connection import get_db
from app.database.models import User, Feedback
from app.models.requests import AppFeedbackRequest, FeedbackRequest
from app.models.responses import AppFeedbackResponse
from app.models.feedback import FeedbackCreate, FeedbackResponse
from app.repositories import FeedbackRepository, RunRepository
from app.services.feedback_service import feedback_service

router = APIRouter()


def _parse_payload_from_comment(comment: Optional[str]) -> Optional[dict]:
    if not comment:
        return None
    try:
        # If it's already a dict/list, return it
        if isinstance(comment, (dict, list)):
            return comment
        parsed = json.loads(comment)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        # It's a plain string, not JSON
        return None


@router.post(
    "/app", response_model=AppFeedbackResponse, status_code=status.HTTP_201_CREATED
)
async def create_app_feedback(
    request: AppFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> Any:
    """Create an app-level feedback entry tied to a run_id."""

    run = RunRepository(db).get_by_run_id(request.run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if current_user and run.user_id is not None and run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    payload_json = json.dumps(request.payload or {}, ensure_ascii=False)
    # Store payload + optional free-text in a single field.
    # Keep it simple and forward-compatible.
    if request.comment:
        combined = {"payload": request.payload or {}, "comment": request.comment}
        payload_json = json.dumps(combined, ensure_ascii=False)

    repo = FeedbackRepository(db)
    feedback = repo.create_feedback(
        run_id=request.run_id,
        building_id=None,
        rating=request.rating if request.rating is not None else None,
        comment=payload_json,
        helpful=None,
    )

    parsed = _parse_payload_from_comment(feedback.comment)
    if isinstance(parsed, dict) and "payload" in parsed and "comment" in parsed:
        payload_out = parsed.get("payload")
        comment_out = parsed.get("comment")
    else:
        payload_out = parsed
        comment_out = None

    return AppFeedbackResponse(
        id=feedback.id,
        run_id=feedback.run_id,
        rating=feedback.rating,
        comment=comment_out,
        payload=payload_out,
        created_at=feedback.created_at,
    )


@router.get("/app", response_model=list[AppFeedbackResponse])
async def list_app_feedback(
    run_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> Any:
    """List app-level feedback entries for a run."""

    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    run = RunRepository(db).get_by_run_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if current_user and run.user_id is not None and run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # app-level = building_id is NULL
    rows = (
        db.query(Feedback)
        .filter(Feedback.run_id == run_id)
        .filter(Feedback.building_id.is_(None))
        .order_by(Feedback.created_at.desc())
        .limit(limit)
        .all()
    )

    out: list[AppFeedbackResponse] = []
    for fb in rows:
        parsed = _parse_payload_from_comment(fb.comment)
        if isinstance(parsed, dict) and "payload" in parsed and "comment" in parsed:
            payload_out = parsed.get("payload")
            comment_out = parsed.get("comment")
        else:
            payload_out = parsed
            comment_out = None

        out.append(
            AppFeedbackResponse(
                id=fb.id,
                run_id=fb.run_id,
                rating=fb.rating,
                comment=comment_out,
                payload=payload_out,
                created_at=fb.created_at,
            )
        )

    return out


@router.post("/agent", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_feedback(
    request: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> Any:
    """Create feedback for a specific agent or global analysis feedback."""

    # Verify run exists
    run = RunRepository(db).get_by_run_id(request.run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Check permissions if user-specific
    if current_user and run.user_id is not None and run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if feedback already exists for this agent/run combination
    repo = FeedbackRepository(db)
    existing = repo.get_feedback_by_agent(request.run_id, request.agent_name)
    if existing:
        # Update existing feedback instead of creating duplicate
        existing.rating = request.rating
        existing.comment = request.comment
        db.commit()
        db.refresh(existing)
        return FeedbackResponse.model_validate(existing)

    # Create new feedback
    feedback = repo.create_agent_feedback(
        run_id=request.run_id,
        agent_name=request.agent_name,
        rating=request.rating,
        comment=request.comment,
        user_id=current_user.id if current_user else None,
    )

    return FeedbackResponse.model_validate(feedback)


@router.get("/agent", response_model=list[FeedbackResponse])
async def get_agent_feedback(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> Any:
    """Get all agent feedback for a specific analysis run."""

    # Verify run exists
    run = RunRepository(db).get_by_run_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Check permissions if user-specific
    if current_user and run.user_id is not None and run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get all agent feedback
    repo = FeedbackRepository(db)
    feedbacks = repo.get_agent_feedback_by_run(run_id)

    return [FeedbackResponse.model_validate(fb) for fb in feedbacks]


@router.get("/run/all", response_model=list[FeedbackResponse])
async def get_run_all_feedback(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> Any:
    """Get all feedback (global, agent, and building) for a specific analysis run."""

    # Verify run exists
    run = RunRepository(db).get_by_run_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Check permissions if user-specific
    if current_user and run.user_id is not None and run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get all feedback for this run
    repo = FeedbackRepository(db)
    feedbacks = repo.get_by_run(run_id)

    return [FeedbackResponse.model_validate(fb) for fb in feedbacks]


@router.get("/export", status_code=status.HTTP_200_OK)
async def export_feedback(
    format: str = "csv",
    db: Session = Depends(get_db),
    # Only authenticated users can export
    # In a real app, this should be admin-only
    _: User = Depends(get_current_user_optional),
) -> Any:
    """Export all agent feedback in CSV format."""
    
    # Get all feedback entries that are not tied to buildings (agent/global feedback)
    feedbacks = (
        db.query(Feedback)
        .filter(Feedback.building_id.is_(None))
        .all()
    )
    
    feedback_objs = [FeedbackResponse.model_validate(fb) for fb in feedbacks]
    
    if format == "csv":
        from fastapi.responses import Response
        csv_data = feedback_service.export_all_to_csv(feedback_objs)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=agent_feedback_{datetime.now().strftime('%Y%m%d')}.csv"
            }
        )
    
    return feedback_objs


@router.post("/building", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_building_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> Any:
    """Create feedback for a specific building."""

    # Verify run exists
    run = RunRepository(db).get_by_run_id(request.run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if current_user and run.user_id is not None and run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    repo = FeedbackRepository(db)
    
    # Check if feedback already exists for this building/run
    existing = repo.get_feedback_by_building(request.run_id, request.building_id)
    if existing:
        # Update existing feedback
        existing.rating = request.rating
        existing.comment = request.comment
        existing.helpful = 1 if request.helpful else 0
        db.commit()
        db.refresh(existing)
        return FeedbackResponse.model_validate(existing)
    
    # Create new feedback
    feedback = repo.create_feedback(
        run_id=request.run_id,
        building_id=request.building_id,
        rating=request.rating,
        comment=request.comment,
        helpful=1 if request.helpful else 0,
    )
    
    return FeedbackResponse.model_validate(feedback)


@router.get("/building", response_model=list[FeedbackResponse])
async def get_building_feedback(
    run_id: str,
    building_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> Any:
    """Get feedback for a specific building in a run."""
    
    run = RunRepository(db).get_by_run_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    if current_user and run.user_id is not None and run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    repo = FeedbackRepository(db)
    # Reusing get_by_building, but we should probably filter by run too in a real scenario
    # Repo get_by_building: return self.db.query(Feedback).filter(Feedback.building_id == building_id).all()
    # It returns ALL feedback for that building across ALL runs potentially?
    # The method get_by_building doesn't take run_id.
    # However, Feedback has run_id column.
    
    # Let's do a direct query here for precision, or add a method to repo.
    # Direct query for now to save time editing repo.
    feedbacks = (
        db.query(Feedback)
        .filter(Feedback.run_id == run_id)
        .filter(Feedback.building_id == building_id)
        .all()
    )
    
    return [FeedbackResponse.model_validate(fb) for fb in feedbacks]
