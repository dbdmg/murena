"""
Run repository for analysis run operations.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.models import Run
from app.repositories.base import BaseRepository


class RunRepository(BaseRepository[Run]):
    """Repository for Run model operations."""

    def __init__(self, db: Session):
        """Initialize with Run model."""
        super().__init__(Run, db)

    def get_by_run_id(self, run_id: str) -> Optional[Run]:
        """
        Get run by unique run_id.

        Args:
            run_id: Unique run identifier

        Returns:
            Run instance or None if not found
        """
        return self.db.query(Run).filter(Run.run_id == run_id).first()

    def get_user_runs(self, user_id: int, limit: int = 50) -> List[Run]:
        """
        Get runs for a specific user, ordered by most recent first.

        Args:
            user_id: User ID
            limit: Maximum number of runs to return

        Returns:
            List of Run instances
        """
        return (
            self.db.query(Run)
            .filter(Run.user_id == user_id)
            .order_by(desc(Run.created_at))
            .limit(limit)
            .all()
        )

    def create_run(
        self,
        run_id: str,
        query: str,
        user_id: Optional[int] = None,
        dataset_key: str = "full",
        analysis_mode: str = "agent",
    ) -> Run:
        """
        Create a new analysis run.

        Args:
            run_id: Unique run identifier
            query: User's search query
            user_id: Optional user ID
            dataset_key: Dataset to use
            analysis_mode: Analysis mode ('agent' or 'classic')

        Returns:
            Created Run instance
        """
        run = Run(
            run_id=run_id,
            query=query,
            user_id=user_id,
            dataset_key=dataset_key,
            analysis_mode=analysis_mode,
            status="processing",
        )
        return self.create(run)

    def update_status(
        self,
        run_id: str,
        status: str,
        results: Optional[Dict[str, Any]] = None,
        status_message: Optional[str] = None,
    ) -> Optional[Run]:
        """
        Update run status and optionally results.

        Args:
            run_id: Unique run identifier
            status: New status ('processing', 'completed', 'failed')
            results: Optional results data
            status_message: Optional status message

        Returns:
            Updated Run instance or None if not found
        """
        run = self.get_by_run_id(run_id)
        if run:
            run.status = status
            if results is not None:
                run.results = results
            if status_message is not None:
                run.status_message = status_message
            if status in ["completed", "failed"]:
                run.completed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(run)
        return run

    def save_complete_results(
        self,
        run_id: str,
        results: Dict[str, Any],
        gemini_responses: Dict[str, Any],
        location_data: Any,
        status_message: str,
        results_count: int,
    ) -> Optional[Run]:
        """
        Save complete analysis results for a run.

        Args:
            run_id: Unique run identifier
            results: Analysis results
            gemini_responses: LLM responses
            location_data: Geographic location data
            status_message: Status message
            results_count: Number of results

        Returns:
            Updated Run instance or None if not found
        """
        run = self.get_by_run_id(run_id)
        if run:
            run.status = "completed"
            run.results = results
            run.gemini_responses = gemini_responses
            run.location_data = location_data
            run.status_message = status_message
            run.results_count = results_count
            run.completed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(run)
        return run

    def get_recent_runs(self, limit: int = 20) -> List[Run]:
        """
        Get most recent runs across all users.

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of Run instances
        """
        return self.db.query(Run).order_by(desc(Run.created_at)).limit(limit).all()
