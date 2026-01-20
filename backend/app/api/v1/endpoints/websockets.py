"""
WebSocket endpoints for real-time communication.

Provides:
- Real-time analysis progress updates
- Completion notifications
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.progress_manager import progress_manager
from app.utils.logger import logger

router = APIRouter()


@router.websocket("/ws/analysis/{run_id}")
async def analysis_progress_websocket(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for real-time analysis progress updates.

    Clients connect with a run_id and receive:
    - Progress updates during analysis execution
    - Completion message when analysis finishes

    **Connection URL:** `ws://localhost:8000/api/v1/ws/analysis/{run_id}`

    **Message Types:**

    1. **Progress Update:**
    ```json
    {
        "type": "progress",
        "progress": 45,
        "step": "sql",
        "detail": "Generating SQL query...",
        "steps_state": [...]
    }
    ```

    2. **Completion:**
    ```json
    {
        "type": "complete",
        "run_id": "abc123",
        "message": "Analysis completed",
        "results_url": "/api/v1/analysis/abc123"
    }
    ```

    **Usage Example (JavaScript):**
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/ws/analysis/abc123');

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Progress:', data.progress + '%');

        if (data.type === 'complete') {
            console.log('Analysis complete!');
        }
    };
    ```

    Args:
        websocket: WebSocket connection
        run_id: Analysis run identifier to subscribe to
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for run: {run_id}")

    try:
        # Subscribe to progress updates
        message_count = 0
        async for update in progress_manager.subscribe(run_id):
            # Send update to client
            await websocket.send_json(update.model_dump())
            message_count += 1

        # Send final completion message
        completion_message = {
            "type": "complete",
            "run_id": run_id,
            "message": "Analysis completed successfully",
            "results_url": f"/api/v1/analysis/{run_id}",
        }
        await websocket.send_json(completion_message)

        logger.info(
            f"WebSocket completed for run {run_id} " f"({message_count} updates sent)"
        )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for run: {run_id}")

    except Exception as e:
        logger.error(f"WebSocket error for run {run_id}: {e}", exc_info=True)

        # Try to send error message to client
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "run_id": run_id,
                    "message": "An error occurred during streaming",
                    "error": str(e),
                }
            )
        except:
            pass

    finally:
        # Ensure connection is closed
        try:
            await websocket.close()
        except:
            pass
