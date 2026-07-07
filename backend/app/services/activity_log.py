"""In-process activity log.

Captures everything the application logs (agents, SQL, services, errors) into
a bounded in-memory ring buffer that the frontend can poll via
``GET /api/v1/logs/stream``. This makes MURENA's behaviour inspectable live
from the UI without touching the persistent agent traces (AgentLogger), which
remain the source of truth for per-run deep dives.
"""

from __future__ import annotations

import itertools
import logging
import threading
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

_MAX_ENTRIES = 2000

_lock = threading.Lock()
_buffer: deque = deque(maxlen=_MAX_ENTRIES)
_counter = itertools.count(1)


def log_event(level: str, source: str, message: str,
              data: Optional[Dict[str, Any]] = None) -> None:
    """Append a structured event to the activity log."""
    with _lock:
        _buffer.append({
            "id": next(_counter),
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "level": level.upper(),
            "source": source,
            "message": message,
            "data": data,
        })


def get_events(since_id: int = 0, limit: int = 500,
               level: Optional[str] = None,
               source: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return events with id > since_id, newest last."""
    with _lock:
        events = list(_buffer)
    if since_id:
        events = [e for e in events if e["id"] > since_id]
    if level:
        wanted = {l.strip().upper() for l in level.split(",")}
        events = [e for e in events if e["level"] in wanted]
    if source:
        needle = source.lower()
        events = [e for e in events if needle in e["source"].lower()]
    return events[-limit:]


class ActivityLogHandler(logging.Handler):
    """Standard-logging handler feeding the ring buffer."""

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover
        try:
            log_event(record.levelname, record.name, record.getMessage())
        except Exception:
            pass


class _LoguruSink:
    """Loguru sink feeding the ring buffer (app.utils.logger uses loguru)."""

    def __call__(self, message) -> None:  # pragma: no cover
        try:
            record = message.record
            src = record["name"] or "app"
            log_event(record["level"].name, src, record["message"])
        except Exception:
            pass


def install(app_logger=None) -> None:
    """Attach the activity log to both stdlib logging and loguru."""
    root = logging.getLogger()
    if not any(isinstance(h, ActivityLogHandler) for h in root.handlers):
        handler = ActivityLogHandler(level=logging.INFO)
        root.addHandler(handler)

    try:
        from app.utils.logger import logger as loguru_logger
        loguru_logger.add(_LoguruSink(), level="INFO",
                          format="{message}", enqueue=False)
    except Exception:
        pass

    log_event("INFO", "activity_log", "Activity log initialised")
