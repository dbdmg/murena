"""Prompt override API endpoints.

These endpoints expose the markdown-based prompt override system used by LLM agents.
They are intended for development/expert workflows (e.g. viewing/editing templates).
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user_optional
from app.core.config import settings
from app.database.models import User
from app.services.llm import prompt_loader

router = APIRouter()


class PromptUpdateRequest(BaseModel):
    text: str = Field(..., description="New prompt template content")


@router.get("/overrides")
async def list_prompt_overrides() -> Dict[str, Dict[str, str]]:
    """List all prompt overrides loaded from prompt_config.md."""

    try:
        return prompt_loader._load_overrides()  # best-effort: shared cache
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load prompt overrides: {e}"
        )


@router.get("/overrides/{agent}/{key}", response_model=None)
async def get_prompt_override(agent: str, key: str = "template") -> Dict[str, Any] | JSONResponse:
    """Get a single override block (if present)."""

    try:
        overrides = prompt_loader._load_overrides()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load prompt overrides: {e}"
        )

    agent_map = overrides.get(agent)
    if not agent_map or key not in agent_map:
        return JSONResponse(status_code=404, content={"detail": "Prompt override not found"})

    return {"agent": agent, "key": key, "text": agent_map[key]}


@router.put("/overrides/{agent}/{key}")
async def put_prompt_override(
    agent: str,
    key: str,
    request: PromptUpdateRequest,
    current_user: User | None = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """Create/update an override block inside prompt_config.md.

    In non-debug environments this is forbidden.
    """

    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Prompt editing is disabled")

    # If auth exists, keep it permissive for now (dev/expert tooling).
    _ = current_user

    try:
        prompt_loader.update_prompt_template(
            agent=agent, key=key, new_text=request.text
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update prompt override: {e}"
        )

    return {
        "agent": agent,
        "key": key,
        "text": prompt_loader.get_prompt_template(agent=agent, key=key, default=""),
    }


@router.post("/reload")
async def reload_prompt_overrides() -> Dict[str, str]:
    """Reload prompt override cache."""

    prompt_loader.reload_prompt_cache()
    return {
        "status": "ok",
        "message": "Prompt cache reloaded from prompt_config.md",
    }


@router.post("/reset")
async def reset_prompt_overrides() -> Dict[str, str]:
    """Backward-compatible alias for reloading prompt_config.md.

    The project currently stores prompts directly in prompt_config.md, so there
    is no separate defaults file to restore from.
    """

    return await reload_prompt_overrides()


@router.post("/reset/{agent}")
async def reset_agent_prompt_overrides(agent: str) -> Dict[str, str]:
    """Backward-compatible alias used by older frontend builds."""

    prompt_loader.reload_prompt_cache()
    if agent and not prompt_loader.get_agent_prompts(agent):
        raise HTTPException(status_code=404, detail=f"Prompt agent not found: {agent}")
    return {
        "status": "ok",
        "message": f"Prompt cache reloaded from prompt_config.md for {agent}",
    }


@router.get("/agents")
async def list_available_agents() -> Dict[str, Any]:
    """List all available agents with their prompt keys."""

    try:
        agents = prompt_loader.get_available_agents()
        agent_details = {}
        overrides = prompt_loader._load_overrides()
        for agent in agents:
            agent_details[agent] = list(overrides.get(agent, {}).keys())
        return {"agents": agent_details}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {e}")
