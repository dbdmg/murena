"""LLM-generated example searches for the search landing page."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

from pydantic import BaseModel, Field

from app.services.llm.langchain_client import get_llm
from app.services.llm.prompt_loader import get_system_prompt


class SuggestedSearches(BaseModel):
    suggestions: list[str] = Field(
        description="Exactly five distinct English property-search queries"
    )


_NORMATIVE_FILE = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "knowledge"
    / "normativa"
    / "normativa.json"
)
_TURIN_AREAS_FILE = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "knowledge"
    / "turin_areas.json"
)
_CACHE_TTL_SECONDS = 30 * 60
_CACHE_LOCK = threading.Lock()
_CACHE_KEY: tuple[int, int, int, int, str] | None = None
_CACHE_EXPIRES_AT = 0.0
_CACHE_SUGGESTIONS: list[str] | None = None


def generate_suggested_searches() -> list[str]:
    """Generate five English searches and cache them until sources change or expire."""
    global _CACHE_KEY, _CACHE_EXPIRES_AT, _CACHE_SUGGESTIONS

    normative_stat = _NORMATIVE_FILE.stat()
    areas_stat = _TURIN_AREAS_FILE.stat()
    system_prompt = get_system_prompt("suggested_searches")
    if not system_prompt.strip():
        raise RuntimeError("Suggested-search prompt is not configured")
    prompt_hash = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
    cache_key = (
        normative_stat.st_mtime_ns,
        normative_stat.st_size,
        areas_stat.st_mtime_ns,
        areas_stat.st_size,
        prompt_hash,
    )

    with _CACHE_LOCK:
        now = time.monotonic()
        if (
            _CACHE_KEY == cache_key
            and _CACHE_SUGGESTIONS is not None
            and now < _CACHE_EXPIRES_AT
        ):
            return list(_CACHE_SUGGESTIONS)

        records = json.loads(_NORMATIVE_FILE.read_text(encoding="utf-8"))
        area_groups = json.loads(_TURIN_AREAS_FILE.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("Regulatory use-case data must be a JSON array")
        if not isinstance(area_groups, list):
            raise ValueError("Turin area data must be a JSON array")
        areas = [
            area
            for group in area_groups
            if isinstance(group, dict) and isinstance(group.get("areas"), list)
            for area in group["areas"]
            if isinstance(area, str) and area.strip()
        ]
        if not areas:
            raise ValueError("No Turin areas are available")
        use_cases = [
            {"use_case": item["use_case"], "sector": item.get("sector", "")}
            for item in records
            if isinstance(item, dict) and isinstance(item.get("use_case"), str)
        ]
        if not use_cases:
            raise ValueError("No regulatory use cases are available")

        prompt = (
            f"{system_prompt.strip()}\n\n"
            "Regulatory use cases available in the project (JSON):\n"
            f"{json.dumps(use_cases, ensure_ascii=False)}\n\n"
            "Official Turin areas available for suggestions (JSON):\n"
            f"{json.dumps(areas, ensure_ascii=False)}\n\n"
            "Search capabilities: natural-language filters for property type and intended use, "
            "location or landmark, floor area, energy performance, building constraints, and "
            "nearby service categories such as healthcare, mobility, green spaces, sport, "
            "commerce, and education."
        )
        model = get_llm(temperature=0.7)
        structured_model = model.with_structured_output(SuggestedSearches)
        suggestions = None
        for attempt in range(2):
            retry_instruction = (
                "\n\nCorrection: regenerate all five queries. Each query must include the exact "
                "name of one area from the supplied official Turin area list. Turin is implicit; "
                "do not add the city name unless it is a natural part of a landmark or place name. "
                "Do not use any area outside the supplied list."
                if attempt
                else ""
            )
            result = structured_model.invoke(prompt + retry_instruction)
            generated = (
                result.suggestions
                if isinstance(result, SuggestedSearches)
                else SuggestedSearches.model_validate(result).suggestions
            )
            generated = [item.strip() for item in generated if item.strip()]
            if (
                len(generated) == 5
                and len({item.casefold() for item in generated}) == 5
                and all(
                    any(area.casefold() in item.casefold() for area in areas)
                    for item in generated
                )
            ):
                suggestions = generated
                break
        if suggestions is None:
            raise ValueError(
                "The model must return five distinct searches that name an area from the supplied list"
            )

        _CACHE_KEY = cache_key
        _CACHE_EXPIRES_AT = now + _CACHE_TTL_SECONDS
        _CACHE_SUGGESTIONS = suggestions
        return list(suggestions)
