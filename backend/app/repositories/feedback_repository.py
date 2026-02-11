"""
Feedback repository for user feedback operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.database.models import Feedback
from app.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[Feedback]):
    """Repository for Feedback model operations."""

    def __init__(self, db: Session):
        """Initialize with Feedback model."""
        super().__init__(Feedback, db)

    def get_by_building(self, building_id: str) -> List[Feedback]:
        """
        Get all feedback for a specific building.

        Args:
            building_id: Building ID to search for

        Returns:
            List of Feedback instances
        """
        return self.db.query(Feedback).filter(Feedback.building_id == building_id).all()

    def get_by_run(self, run_id: str) -> List[Feedback]:
        """
        Get all feedback for a specific run.

        Args:
            run_id: Run ID to search for

        Returns:
            List of Feedback instances
        """
        return self.db.query(Feedback).filter(Feedback.run_id == run_id).all()

    def create_feedback(
        self,
        run_id: str,
        building_id: Optional[str],
        rating: Optional[int],
        comment: Optional[str] = None,
        helpful: Optional[int] = None,
    ) -> Feedback:
        """
        Create new feedback for a building.

        Args:
            run_id: Run ID
            building_id: Building ID
            rating: Rating (1-5)
            comment: Optional text comment
            helpful: Optional helpful indicator (0=no, 1=yes)

        Returns:
            Created Feedback instance
        """
        feedback = Feedback(
            run_id=run_id,
            building_id=building_id,
            rating=rating,
            comment=comment,
            helpful=helpful,
        )
        return self.create(feedback)

    def update_feedback(
        self,
        feedback_id: int,
        rating: Optional[int] = None,
        comment: Optional[str] = None,
        helpful: Optional[int] = None,
        **evaluation_fields,
    ) -> Optional[Feedback]:
        """
        Update existing feedback.

        Args:
            feedback_id: Feedback ID
            rating: Optional new rating
            comment: Optional new comment
            helpful: Optional new helpful value
            **evaluation_fields: Additional evaluation fields (e1-e5)

        Returns:
            Updated Feedback instance or None if not found
        """
        feedback = self.get(feedback_id)
        if feedback:
            if rating is not None:
                feedback.rating = rating
            if comment is not None:
                feedback.comment = comment
            if helpful is not None:
                feedback.helpful = helpful

            # Update evaluation fields
            for key, value in evaluation_fields.items():
                if hasattr(feedback, f"feedback_{key}"):
                    setattr(feedback, f"feedback_{key}", value)

            self.db.commit()
            self.db.refresh(feedback)
        return feedback

    def get_building_rating_average(self, building_id: str) -> Optional[float]:
        """
        Calculate average rating for a building.

        Args:
            building_id: Building ID

        Returns:
            Average rating or None if no feedback exists
        """
        from sqlalchemy import func

        result = (
            self.db.query(func.avg(Feedback.rating))
            .filter(Feedback.building_id == building_id)
            .scalar()
        )

        return float(result) if result is not None else None

    def create_agent_feedback(
        self,
        run_id: str,
        agent_name: Optional[str],
        rating: int,
        comment: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Feedback:
        """
        Create new feedback for an agent or global feedback.

        Args:
            run_id: Run ID
            agent_name: Agent name (None for global feedback)
            rating: Rating (1-5)
            comment: Optional text comment
            user_id: Optional user ID

        Returns:
            Created Feedback instance
        """
        feedback = Feedback(
            run_id=run_id,
            agent_name=agent_name,
            rating=rating,
            comment=comment,
            user_id=user_id,
        )
        return self.create(feedback)

    def get_agent_feedback_by_run(self, run_id: str) -> List[Feedback]:
        """
        Get all agent feedback for a specific run.

        Args:
            run_id: Run ID to search for

        Returns:
            List of Feedback instances for agents
        """
        return (
            self.db.query(Feedback)
            .filter(Feedback.run_id == run_id)
            .filter(Feedback.agent_name.isnot(None) | (Feedback.agent_name.is_(None) & Feedback.building_id.is_(None)))
            .all()
        )

    def get_feedback_by_agent(
        self, run_id: str, agent_name: Optional[str]
    ) -> Optional[Feedback]:
        """
        Get feedback for a specific agent or global feedback.

        Args:
            run_id: Run ID
            agent_name: Agent name (None for global feedback)

        Returns:
            Feedback instance or None
        """
        query = self.db.query(Feedback).filter(Feedback.run_id == run_id)
        if agent_name is None:
            query = query.filter(Feedback.agent_name.is_(None), Feedback.building_id.is_(None))
        else:
            query = query.filter(Feedback.agent_name == agent_name)
        return query.first()

    def get_feedback_by_building(
        self, run_id: str, building_id: str
    ) -> Optional[Feedback]:
        """
        Get feedback for a specific building in a run.

        Args:
            run_id: Run ID
            building_id: Building ID

        Returns:
            Feedback instance or None
        """
        return (
            self.db.query(Feedback)
            .filter(Feedback.run_id == run_id)
            .filter(Feedback.building_id == building_id)
            .first()
        )
