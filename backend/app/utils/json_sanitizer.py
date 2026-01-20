"""Utilities to convert arbitrary objects into JSON-serializable Python types.

FastAPI/Pydantic JSON serialization does not support some scientific Python types
(e.g. numpy.ndarray). This module provides a best-effort recursive sanitizer
used at API boundaries and persistence points.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any


def make_json_safe(value: Any) -> Any:
    """Best-effort conversion to JSON-serializable types.

    Rules:
    - Basic JSON scalars are returned as-is.
    - dict/list/tuple/set are sanitized recursively.
    - numpy.ndarray -> list via tolist().
    - numpy scalar -> Python scalar via item().
    - pandas Series/DataFrame -> dict/records.
    - datetime/date -> isoformat string.
    - Path -> str.
    - Unknown objects -> str(value).

    This is intended for logging/persistence and API responses, not for
    preserving exact types.
    """

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Path):
        return str(value)

    # Pydantic models (v1/v2)
    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
        try:
            dumped = value.model_dump(mode="python")
            return make_json_safe(dumped)
        except Exception:
            pass

    # numpy arrays / scalars (avoid hard dependency)
    module = type(value).__module__
    name = type(value).__name__
    if module.startswith("numpy"):
        if name == "ndarray" and hasattr(value, "tolist"):
            try:
                return make_json_safe(value.tolist())
            except Exception:
                return []
        if hasattr(value, "item") and callable(getattr(value, "item")):
            try:
                return make_json_safe(value.item())
            except Exception:
                return str(value)

    # pandas (avoid hard dependency)
    if module.startswith("pandas"):
        if name in {"Series"} and hasattr(value, "to_dict"):
            try:
                return make_json_safe(value.to_dict())
            except Exception:
                return {}
        if name in {"DataFrame"} and hasattr(value, "to_dict"):
            try:
                return make_json_safe(value.to_dict(orient="records"))
            except Exception:
                return []

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = k if isinstance(k, str) else str(k)
            out[key] = make_json_safe(v)
        return out

    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(v) for v in list(value)]

    # Objects that look like numpy arrays without being numpy (duck typing)
    if hasattr(value, "tolist") and callable(getattr(value, "tolist")):
        try:
            return make_json_safe(value.tolist())
        except Exception:
            pass

    return str(value)
