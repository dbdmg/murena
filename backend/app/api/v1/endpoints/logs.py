"""Activity-log endpoints.

Expose everything MURENA does so its behaviour can be inspected from the
frontend:

- ``GET /logs/stream``          live in-process events (poll with ?since_id=)
- ``GET /logs/traces``          list of persisted per-run agent trace files
- ``GET /logs/traces/{name}``   content of one agent trace (JSON)
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.services.activity_log import get_events

router = APIRouter()


def _traces_dir() -> Path:
    base = Path(__file__).resolve().parents[4]  # -> backend/
    return (base / settings.AGENT_LOGS_DIR).resolve()


@router.get("/stream")
async def stream_activity_log(
    since_id: int = Query(0, description="Return only events with id greater than this"),
    limit: int = Query(500, le=2000),
    level: Optional[str] = Query(None, description="Comma-separated levels, e.g. INFO,ERROR"),
    source: Optional[str] = Query(None, description="Substring filter on the logger name"),
) -> Dict[str, Any]:
    """Recent in-process activity events (agents, SQL, services, errors)."""
    events = get_events(since_id=since_id, limit=limit, level=level, source=source)
    return {
        "events": events,
        "last_id": events[-1]["id"] if events else since_id,
    }


@router.get("/traces")
async def list_agent_traces() -> List[Dict[str, Any]]:
    """List persisted agent-trace files (one JSON per analysis run)."""
    traces_dir = _traces_dir()
    if not traces_dir.exists():
        return []
    items = []
    for f in sorted(traces_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
        items.append({
            "name": f.name,
            "size_bytes": f.stat().st_size,
            "modified_at": f.stat().st_mtime,
        })
    return items[:200]


@router.get("/traces/{name}")
async def get_agent_trace(name: str) -> Dict[str, Any]:
    """Return the content of one persisted agent trace."""
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid trace name")
    path = _traces_dir() / name
    if not path.exists() or path.suffix != ".json":
        raise HTTPException(status_code=404, detail="Trace not found")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unreadable trace: {e}")
