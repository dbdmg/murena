"""
Progress Manager - Coordinates progress updates between analysis tasks and WebSocket clients.

This module provides:
- AsyncIO Queue-based progress streaming
- Support for multiple clients subscribing to same run
- Automatic cleanup after completion
- Thread-safe progress publishing
"""

import asyncio
from typing import Dict, List, AsyncGenerator, Optional
from collections import defaultdict

from app.models.responses import ProgressUpdate
from app.utils.logger import logger


class ProgressManager:
    """Manages progress updates for analysis runs using AsyncIO queues."""

    def __init__(self):
        """Initialize the progress manager."""
        # run_id → list of client queues
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        # run_id → last known progress update
        self._last_state: Dict[str, ProgressUpdate] = {}
        # run_id → whether the run is finished
        self._completed: Dict[str, bool] = {}
        self._lock = asyncio.Lock()
        logger.info("ProgressManager initialized")

    async def subscribe(self, run_id: str) -> AsyncGenerator[ProgressUpdate, None]:
        """
        Subscribe to progress updates for a specific run.

        Args:
            run_id: Analysis run identifier

        Yields:
            ProgressUpdate objects as they are published
        """
        queue: asyncio.Queue = asyncio.Queue()

        # Register subscriber
        async with self._lock:
            self._subscribers[run_id].append(queue)
            subscriber_count = len(self._subscribers[run_id])
            
            # Send current state if available
            last_update = self._last_state.get(run_id)
            is_done = self._completed.get(run_id, False)

        logger.info(
            f"Client subscribed to run {run_id} ({subscriber_count} total subscribers)"
        )

        # If we have a cached state, send it immediately
        if last_update:
            await queue.put(last_update)
            
        # If already completed, send finish signal immediately
        if is_done:
            await queue.put(None)

        try:
            while True:
                update = await queue.get()

                # None signals completion
                if update is None:
                    logger.debug(f"Completion signal received for run {run_id}")
                    break

                yield update

        finally:
            # Cleanup: remove this queue from subscribers
            async with self._lock:
                if queue in self._subscribers[run_id]:
                    self._subscribers[run_id].remove(queue)
                    remaining = len(self._subscribers[run_id])
                    logger.info(
                        f"Client unsubscribed from run {run_id} ({remaining} remaining)"
                    )

                # If no more subscribers, cleanup the key
                if run_id in self._subscribers and not self._subscribers[run_id]:
                    del self._subscribers[run_id]
                    logger.debug(f"Removed run {run_id} from subscribers (no clients)")

    async def publish(self, run_id: str, update: ProgressUpdate) -> None:
        """
        Publish a progress update to all subscribers of a run.

        Args:
            run_id: Analysis run identifier
            update: Progress update to send
        """
        async with self._lock:
            queues = self._subscribers.get(run_id, [])
            # Cache the latest state
            self._last_state[run_id] = update

        if not queues:
            logger.debug(f"No subscribers for run {run_id}, state cached for future connections")
            return

        # Send update to all subscribers
        for queue in queues:
            try:
                await queue.put(update)
            except Exception as e:
                logger.error(f"Failed to publish update to subscriber: {e}")

        logger.debug(
            f"Published update to {len(queues)} subscriber(s) for run {run_id}"
        )

    async def complete(self, run_id: str) -> None:
        """
        Signal completion to all subscribers and cleanup.

        Args:
            run_id: Analysis run identifier
        """
        async with self._lock:
            queues = self._subscribers.get(run_id, [])
            # Mark as completed
            self._completed[run_id] = True

        if not queues:
            logger.debug(f"No subscribers to complete for run {run_id}, status cached")
            return

        # Send completion signal (None) to all subscribers
        for queue in queues:
            try:
                await queue.put(None)
            except Exception as e:
                logger.error(f"Failed to send completion signal: {e}")

        logger.info(
            f"Sent completion signal to {len(queues)} subscriber(s) for run {run_id}"
        )

        # Cleanup will happen automatically when clients disconnect

    def get_subscriber_count(self, run_id: str) -> int:
        """
        Get the number of active subscribers for a run.

        Args:
            run_id: Analysis run identifier

        Returns:
            Number of active subscribers
        """
        return len(self._subscribers.get(run_id, []))

    def get_active_runs(self) -> List[str]:
        """
        Get list of run IDs with active subscribers.

        Returns:
            List of active run IDs
        """
        return list(self._subscribers.keys())


# Global singleton instance
progress_manager = ProgressManager()
