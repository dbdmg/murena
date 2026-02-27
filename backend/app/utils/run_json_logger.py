"""
Optional JSON logger for run results.
Saves detailed run data to JSON files for easy LLM analysis.

Enable/disable via ENABLE_RUN_JSON_EXPORT in config.py
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app.utils.logger import logger


class RunJSONLogger:
    """Logs run results to JSON files for easy inspection."""

    def __init__(self, export_dir: str = "run_exports"):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def log_run(
        self,
        run_id: str,
        query: str,
        status: str,
        gemini_responses: Dict[str, Any],
        results: Dict[str, Any],
        metrics: Dict[str, Any] = None,
    ) -> None:
        """
        Export run data to JSON file.

        Args:
            run_id: Unique run identifier
            query: User query
            status: Run status (completed, failed, etc.)
            gemini_responses: All agent outputs
            results: Final results (buildings array)
            metrics: Optional computed metrics (APE availability, etc.)
        """
        try:
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{run_id[:8]}.json"
            filepath = self.export_dir / filename

            # Compute metrics if not provided
            if metrics is None:
                metrics = self._compute_metrics(results)

            # Build export data
            export_data = {
                "run_id": run_id,
                "timestamp": timestamp,
                "query": query,
                "status": status,
                "metrics": metrics,
                "agent_outputs": gemini_responses,
                "results_summary": {
                    "total_buildings": len(results.get("buildings", [])),
                    "top_10_ids": [
                        b.get("id") for b in results.get("buildings", [])[:10]
                    ],
                },
                "full_results": results,  # Complete buildings array
            }

            # Sanitize data to handle NaN/None/Infinity
            sanitized_data = self._sanitize_for_json(export_data)

            # Write to file with custom handler for remaining edge cases
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(sanitized_data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f" Run exported to: {filepath}")

            # Keep only last 10 exports (cleanup)
            self._cleanup_old_exports(keep=10)

        except Exception as e:
            logger.error(f"Failed to export run to JSON: {e}")

    def _compute_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Compute useful metrics from results."""
        buildings = results.get("buildings", [])

        if not buildings:
            return {
                "total_buildings": 0,
                "ape_data_available": 0,
                "ape_percentage": 0.0,
                "low_energy_class_count": 0,
            }

        # Count APE data availability
        with_ape = sum(
            1
            for b in buildings
            if b.get("classe_energetica_ape") not in [None, "N/D", ""]
        )

        # Count low energy classes (F, G)
        low_energy = sum(
            1 for b in buildings if b.get("classe_energetica_ape") in ["F", "G"]
        )

        # Count by energy class
        class_distribution = {}
        for b in buildings:
            cls = b.get("classe_energetica_ape", "N/D")
            class_distribution[cls] = class_distribution.get(cls, 0) + 1

        return {
            "total_buildings": len(buildings),
            "ape_data_available": with_ape,
            "ape_percentage": round(100.0 * with_ape / len(buildings), 1),
            "low_energy_class_count": low_energy,
            "low_energy_percentage": round(100.0 * low_energy / len(buildings), 1),
            "energy_class_distribution": class_distribution,
        }

    def _sanitize_for_json(self, obj):
        """
        Recursively sanitize data structures to handle NaN, None, infinity for JSON export.

        Handles:
        - NaN/Infinity → null
        - pandas/numpy types → native Python types
        - Nested dicts/lists
        """
        import math
        import pandas as pd
        import numpy as np

        # Handle pandas types FIRST (before dict/list check)
        if isinstance(obj, pd.Series):
            return self._sanitize_for_json(obj.to_dict())
        elif isinstance(obj, pd.DataFrame):
            return self._sanitize_for_json(obj.to_dict(orient="records"))
        elif isinstance(obj, np.ndarray):
            return self._sanitize_for_json(obj.tolist())
        elif isinstance(obj, dict):
            return {k: self._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_for_json(item) for item in obj]
        elif isinstance(obj, (np.integer, np.floating)):
            # numpy scalar types
            val = obj.item()
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                return None
            return val
        elif isinstance(obj, float):
            # Handle NaN and Infinity
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif obj is None:
            return None
        else:
            return obj

    def _cleanup_old_exports(self, keep: int = 10):
        """Keep only the N most recent exports."""
        try:
            exports = sorted(
                self.export_dir.glob("*.json"), key=os.path.getmtime, reverse=True
            )
            for old_export in exports[keep:]:
                old_export.unlink()
                logger.debug(f"Cleaned up old export: {old_export.name}")
        except Exception as e:
            logger.debug(f"Cleanup failed: {e}")


# Global instance (lazy init)
_run_logger = None


def get_run_logger() -> RunJSONLogger:
    """Get or create the global RunJSONLogger instance."""
    global _run_logger
    if _run_logger is None:
        _run_logger = RunJSONLogger()
    return _run_logger
