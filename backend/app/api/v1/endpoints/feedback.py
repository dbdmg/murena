"""Feedback API endpoints.

For now we support only app-level feedback (not per-building), as it's the
highest value for early frontend iterations.

We store the structured payload as JSON string in Feedback.comment to avoid
schema churn; rating is optional.
"""

from __future__ import annotations

import json
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional
from app.database.connection import get_db
from app.database.models import User, Feedback
from app.models.requests import AppFeedbackRequest
from app.models.responses import AppFeedbackResponse
from app.repositories import FeedbackRepository, RunRepository

router = APIRouter()


def _parse_payload_from_comment(comment: Optional[str]) -> Optional[dict]:
    if not comment:
        return None
    try:
        parsed = json.loads(comment)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
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
