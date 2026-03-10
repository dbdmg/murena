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

# Maximum number of completed run states to keep in memory before purging.
# Prevents unbounded growth when many queries are executed sequentially.
_MAX_COMPLETED_CACHE = 50


class ProgressManager:
    """Manages progress updates for analysis runs using AsyncIO queues."""

    def __init__(self):
        """Initialize the progress manager."""
        # run_id -> list of client queues
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        # run_id -> last known progress update (bounded by _MAX_COMPLETED_CACHE)
        self._last_state: Dict[str, ProgressUpdate] = {}
        # run_id -> whether the run is finished (bounded by _MAX_COMPLETED_CACHE)
        self._completed: Dict[str, bool] = {}
        # Insertion-ordered list of completed run IDs for LRU-style eviction
        self._completed_order: List[str] = []
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

        async with self._lock:
            self._subscribers[run_id].append(queue)
            subscriber_count = len(self._subscribers[run_id])

            last_update = self._last_state.get(run_id)
            is_done = self._completed.get(run_id, False)

        logger.info(
            f"Client subscribed to run {run_id} ({subscriber_count} total subscribers)"
        )

        if last_update:
            await queue.put(last_update)

        if is_done:
            await queue.put(None)

        try:
            while True:
                update = await queue.get()

                if update is None:
                    logger.debug(f"Completion signal received for run {run_id}")
                    break

                yield update

        finally:
            async with self._lock:
                if queue in self._subscribers[run_id]:
                    self._subscribers[run_id].remove(queue)
                    remaining = len(self._subscribers[run_id])
                    logger.info(
                        f"Client unsubscribed from run {run_id} ({remaining} remaining)"
                    )

                if run_id in self._subscribers and not self._subscribers[run_id]:
                    del self._subscribers[run_id]
                    logger.debug(f"Removed run {run_id} from subscribers (no clients)")

                # If the run is also completed and no subscribers remain, drop cached state
                # immediately to reclaim memory rather than waiting for LRU eviction.
                if self._completed.get(run_id) and run_id not in self._subscribers:
                    self._purge_run(run_id)

    async def publish(self, run_id: str, update: ProgressUpdate) -> None:
        """
        Publish a progress update to all subscribers of a run.

        Args:
            run_id: Analysis run identifier
            update: Progress update to send
        """
        async with self._lock:
            queues = list(self._subscribers.get(run_id, []))
            self._last_state[run_id] = update

        if not queues:
            logger.debug(f"No subscribers for run {run_id}, state cached for future connections")
            return

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
        Signal completion to all subscribers and schedule cleanup.

        Args:
            run_id: Analysis run identifier
        """
        async with self._lock:
            queues = list(self._subscribers.get(run_id, []))
            self._completed[run_id] = True
            # Track insertion order for bounded eviction
            if run_id not in self._completed_order:
                self._completed_order.append(run_id)
            # Evict oldest entries when the cache exceeds the limit
            self._evict_if_needed()

        if not queues:
            logger.debug(f"No subscribers to complete for run {run_id}, status cached")
            return

        for queue in queues:
            try:
                await queue.put(None)
            except Exception as e:
                logger.error(f"Failed to send completion signal: {e}")

        logger.info(
            f"Sent completion signal to {len(queues)} subscriber(s) for run {run_id}"
        )

    def _purge_run(self, run_id: str) -> None:
        """
        Remove all cached state for a run.

        Must be called while holding self._lock, or from a context where
        concurrent access is not a concern (e.g. initial startup).
        """
        self._last_state.pop(run_id, None)
        self._completed.pop(run_id, None)
        try:
            self._completed_order.remove(run_id)
        except ValueError:
            pass
        logger.debug(f"Purged state for completed run {run_id}")

    def _evict_if_needed(self) -> None:
        """
        Evict the oldest completed run states if the cache exceeds the limit.

        Called inside publish/complete while holding self._lock.
        Only evicts runs that have no active subscribers.
        """
        while len(self._completed_order) > _MAX_COMPLETED_CACHE:
            oldest = self._completed_order[0]
            # Do not evict if subscribers are still connected
            if oldest in self._subscribers and self._subscribers[oldest]:
                break
            self._purge_run(oldest)

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
