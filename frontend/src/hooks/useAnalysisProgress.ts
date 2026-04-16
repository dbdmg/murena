/**
 * useAnalysisProgress Hook
 *
 * WebSocket hook that connects to the backend to receive real-time
 * progress updates during an analysis run.
 *
 * Usage:
 *   const { progress, isConnected, isComplete } = useAnalysisProgress(runId);
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import type {
    ProgressUpdate,
    ProgressComplete,
    ProgressStep,
    WebSocketMessage,
} from '../api/types';



export interface AnalysisProgressState {
    /** Current progress percentage (0-100) */
    percent: number;
    /** Current step name/label */
    step: string;
    /** Current step states */
    steps: ProgressStep[];
    /** Current status message / detail */
    message: string;
    /** Whether WebSocket is connected */
    isConnected: boolean;
    /** Whether analysis is complete */
    isComplete: boolean;
    /** URL to fetch results (available when complete) */
    resultsUrl: string | null;
    /** Any connection error */
    error: string | null;
}

const initialState: AnalysisProgressState = {
    percent: 0,
    step: '',
    steps: [],
    message: '',
    isConnected: false,
    isComplete: false,
    resultsUrl: null,
    error: null,
};

interface UseAnalysisProgressOptions {
    /** Whether to auto-connect on mount (default: true) */
    autoConnect?: boolean;
    /** Callback when analysis completes */
    onComplete?: (resultsUrl: string) => void;
    /** Callback on connection error */
    onError?: (error: string) => void;
}

export function useAnalysisProgress(
    runId: string | null,
    options: UseAnalysisProgressOptions = {}
) {
    const { autoConnect = true, onComplete, onError } = options;

    const [state, setState] = useState<AnalysisProgressState>(initialState);
    const [retryTrigger, setRetryTrigger] = useState(0);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const reconnectAttemptsRef = useRef(0);
    const isCompleteRef = useRef(false);
    const maxReconnectAttempts = 5;

    // Keep a ref to the current runId so that closures inside WS callbacks
    // always read the latest value without capturing a stale snapshot.
    const runIdRef = useRef<string | null>(runId);
    useEffect(() => {
        runIdRef.current = runId;
    }, [runId]);

    useEffect(() => {
        isCompleteRef.current = state.isComplete;
    }, [state.isComplete]);

    const buildWebSocketUrl = useCallback((id: string) => {
        // VITE_WS_URL can be one of:
        // - ws://host:port (origin)
        // - ws://host:port/api/v1
        // - ws://host:port/api/v1/ws
        // - ws://host:port/ws (legacy)
        let rawBase = (import.meta.env.VITE_WS_URL || '').replace(/\/$/, '');

        // Behavior:
        // 1. If VITE_WS_URL is explicitly set (and not localhost default), use it.
        // 2. If VITE_WS_URL is missing or 'localhost' and we are NOT on localhost, infer from window.location.
        if (!rawBase) {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            // In dev mode, the backend is reachable via the same origin (proxied)
            // or on the configured backend port if we are on localhost.
            rawBase = `${protocol}//${window.location.host}`;
        }

        if (rawBase.includes('/api/v1/ws')) {
            return `${rawBase.replace(/\/$/, '')}/analysis/${id}`;
        }
        if (rawBase.endsWith('/api/v1')) {
            return `${rawBase}/ws/analysis/${id}`;
        }
        if (rawBase.endsWith('/ws')) {
            // Legacy base; best-effort to keep existing configs working.
            return `${rawBase}/analysis/${id}`;
        }

        // Assume origin
        return `${rawBase}/api/v1/ws/analysis/${id}`;
    }, []);

    // Keep callbacks in refs to avoid re-triggering connect when they change (inline literals)
    const onCompleteRef = useRef(onComplete);
    const onErrorRef = useRef(onError);

    useEffect(() => {
        onCompleteRef.current = onComplete;
        onErrorRef.current = onError;
    }, [onComplete, onError]);

    // Connect to WebSocket
    const connect = useCallback(() => {
        if (!runIdRef.current) return;

        // Clear any pending reconnect
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }

        // Close and discard old WebSocket before opening a new one.
        // We set wsRef.current to null BEFORE calling close() so that the
        // old socket's onclose handler can detect that it has been superseded
        // and must not schedule a reconnect or mutate shared state.
        const prevWs = wsRef.current;
        wsRef.current = null;
        if (prevWs && prevWs.readyState !== WebSocket.CLOSED) {
            prevWs.close(1000, 'Superseded by new connection');
        }

        const idForThisSocket = runIdRef.current;
        const ws = new WebSocket(buildWebSocketUrl(idForThisSocket));
        wsRef.current = ws;

        ws.onopen = () => {
            // Guard: make sure this socket is still the active one
            if (wsRef.current !== ws) return;

            reconnectAttemptsRef.current = 0;
            setState((prev) => ({
                ...prev,
                isConnected: true,
                error: null,
            }));
        };

        ws.onmessage = (event) => {
            // Guard: make sure this socket is still the active one
            if (wsRef.current !== ws) return;

            try {
                const data: WebSocketMessage = JSON.parse(event.data);

                if (data.type === 'progress') {
                    const progressData = data as ProgressUpdate;
                    setState((prev) => ({
                        ...prev,
                        percent: progressData.progress,
                        step: progressData.step || '',
                        steps: progressData.steps_state || prev.steps,
                        message: progressData.detail || '',
                    }));
                } else if (data.type === 'complete') {
                    const completeData = data as ProgressComplete;
                    setState((prev) => ({
                        ...prev,
                        percent: 100,
                        isComplete: true,
                        resultsUrl: completeData.results_url,
                    }));

                    onCompleteRef.current?.(completeData.results_url);

                    // Close connection after completion (normal closure)
                    ws.close(1000, 'Analysis complete');
                } else if (data.type === 'error') {
                    console.error('WebSocket reported an error message:', data);
                    setError((data as any).message || 'An error occurred during pipeline execution');
                    setIsConnected(false);
                    // Connection usually closes itself after an error on the backend, but let's be safe
                    ws.close();
                } else {
                    console.warn('Received unexpected message type from WebSocket:', data.type);
                }
            } catch (err) {
                console.error('[WS] Failed to parse message:', err);
            }
        };

        ws.onerror = (event) => {
            // Guard: make sure this socket is still the active one
            if (wsRef.current !== ws) return;

            console.error('[WS] Error:', event);
            const errorMsg = 'WebSocket connection error';
            setState((prev) => ({ ...prev, error: errorMsg }));
            onErrorRef.current?.(errorMsg);
        };

        ws.onclose = (event) => {
            // If this socket has been superseded (wsRef no longer points to it),
            // do not touch shared state or schedule reconnects.
            if (wsRef.current !== ws) return;

            wsRef.current = null;
            setState((prev) => ({ ...prev, isConnected: false }));

            // Attempt reconnect if not completed and not max attempts.
            // Stop on normal closure or 4xxx / fatal server codes.
            if (
                !isCompleteRef.current &&
                reconnectAttemptsRef.current < maxReconnectAttempts &&
                event.code !== 1000 && // Normal closure
                event.code !== 1008 && // Policy violation / auth fail
                event.code !== 1011    // Internal server error (fatal)
            ) {
                reconnectAttemptsRef.current += 1;
                // Exponential backoff with jitter
                const baseDelay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
                const delay = baseDelay + (Math.random() * 1000);

                reconnectTimeoutRef.current = setTimeout(() => {
                    setRetryTrigger(prev => prev + 1);
                }, delay);
            }
        };
    }, [buildWebSocketUrl]);

    // Reconnect when trigger changes
    useEffect(() => {
        if (retryTrigger > 0) {
            connect();
        }
    }, [retryTrigger, connect]);

    // Disconnect and fully discard the current socket
    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }

        const prevWs = wsRef.current;
        wsRef.current = null; // Nullify BEFORE close to suppress the onclose handler
        if (prevWs && prevWs.readyState !== WebSocket.CLOSED) {
            prevWs.close(1000, 'User requested disconnect');
        }

        setState(initialState);
    }, []);

    // Reset state synchronously when runId changes, then connect if needed.
    // Using a synchronous reset (no setTimeout) avoids a race where the new
    // socket's events arrive before the deferred reset clears the old state.
    useEffect(() => {
        setState(initialState);
        isCompleteRef.current = false;
        reconnectAttemptsRef.current = 0;
        setRetryTrigger(0);

        if (autoConnect && runId) {
            connect();
        } else {
            // No new runId — close any open socket
            const prevWs = wsRef.current;
            wsRef.current = null;
            if (prevWs && prevWs.readyState !== WebSocket.CLOSED) {
                prevWs.close(1000, 'Run ID cleared');
            }
        }

        return () => {
            // Cleanup: supersede the current socket so its handlers are inert
            const prevWs = wsRef.current;
            wsRef.current = null;
            if (prevWs && prevWs.readyState !== WebSocket.CLOSED) {
                prevWs.close(1000, 'Component unmounted');
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
                reconnectTimeoutRef.current = null;
            }
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [runId, autoConnect]);

    return {
        ...state,
        connect,
        disconnect,
    };
}

export default useAnalysisProgress;
