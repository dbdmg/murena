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
    """Service to handle feedback storage beyond the database (CSV export)."""

    def __init__(self):
        pass

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
