"""API router aggregating all v1 endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    analysis,
    buildings,
    websockets,
    auth,
    map,
    energy,
    layers,
    prompts,
    feedback,
)

api_router = APIRouter()

# Include routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(buildings.router, tags=["buildings"])
api_router.include_router(websockets.router, tags=["websockets"])
api_router.include_router(map.router, prefix="/map", tags=["map"])
api_router.include_router(energy.router, prefix="/energy", tags=["energy"])
api_router.include_router(layers.router, tags=["layers"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])



# Placeholder routers (will be implemented later)
# api_router.include_router(map.router, prefix="/map", tags=["map"])
# api_router.include_router(energy.router, prefix="/energy", tags=["energy"])
# api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])


@api_router.get("/")
async def api_root():
    """API root endpoint."""
    return {
        "message": "RealEstate-AI API v1",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "auth": "/api/v1/auth",
            "analysis": "/api/v1/analysis",
            "buildings": "/api/v1/buildings",
            "map": "/api/v1/map",
            "websocket": "ws://localhost:8000/api/v1/ws/analysis/{run_id}",
            "health": "/health",
        },
    }
