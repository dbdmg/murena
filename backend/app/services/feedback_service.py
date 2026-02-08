import os
import json
import csv
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from app.core.config import settings
from app.models.feedback import FeedbackResponse
from app.utils.logger import logger

class FeedbackService:
    """Service to handle feedback storage beyond the database (JSON backups, CSV export)."""

    def __init__(self):
        self.base_dir = Path("data/feedback_data")
        self._ensure_dir()

    def _ensure_dir(self):
        """Ensure the feedback data directory exists."""
        if not self.base_dir.exists():
            self.base_dir.mkdir(parents=True, exist_ok=True)

    def backup_to_json(self, run_id: str, feedbacks: List[FeedbackResponse], query: Optional[str] = None):
        """
        Backup all feedback for a specific run into a JSON file.
        Format: data/feedback_data/YYYY-MM/DD/{run_id}.json
        """
        now = datetime.now()
        month_dir = self.base_dir / now.strftime("%Y-%m")
        day_dir = month_dir / now.strftime("%d")
        day_dir.mkdir(parents=True, exist_ok=True)

        file_path = day_dir / f"{run_id}.json"
        
        data = {
            "run_id": run_id,
            "query": query,
            "updated_at": now.isoformat(),
            "feedbacks": [fb.model_dump() for fb in feedbacks]
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Feedback backup saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save feedback backup: {e}")

    def export_all_to_csv(self, feedbacks: List[FeedbackResponse]) -> str:
        """
        Export a list of feedback objects to a CSV string.
        """
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "ID", "Run ID", "Agent Name", "Rating", "Comment", "Created At", "User ID"
        ])
        
        for fb in feedbacks:
            writer.writerow([
                fb.id,
                fb.run_id,
                fb.agent_name if fb.agent_name else "GLOBAL",
                fb.rating,
                fb.comment if fb.comment else "",
                fb.created_at.isoformat(),
                fb.user_id if fb.user_id else ""
            ])
            
        return output.getvalue()

feedback_service = FeedbackService()
