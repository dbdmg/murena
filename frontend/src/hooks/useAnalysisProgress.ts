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

    useEffect(() => {
        isCompleteRef.current = state.isComplete;
    }, [state.isComplete]);

    // Connect to WebSocket
    const connect = useCallback(() => {
        if (!runId) return;

        // Clear any pending reconnect
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
        }

        // Cleanup existing
        if (wsRef.current) {
            wsRef.current.close();
        }

        const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
        const ws = new WebSocket(`${wsUrl}/analysis/${runId}/progress`);
        wsRef.current = ws; // Assign immediately

        console.log(`[WS] Connecting to ${ws.url}`);

        ws.onopen = () => {
            console.log('[WS] Connected');
            reconnectAttemptsRef.current = 0;
            setState((prev) => ({
                ...prev,
                isConnected: true,
                error: null,
            }));
        };

        ws.onmessage = (event) => {
            try {
                const data: WebSocketMessage = JSON.parse(event.data);
                console.log('[WS] Message:', data);

                if (data.type === 'progress') {
                    const progressData = data as ProgressUpdate;
                    setState((prev) => ({
                        ...prev,
                        percent: progressData.progress,
                        step: progressData.step || '',
                        steps: progressData.steps_state || prev.steps, // Use 'steps' to match AnalysisProgressState
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

                    onComplete?.(completeData.results_url);

                    // Close connection after completion
                    ws.close(1000, 'Analysis complete'); // Normal closure
                }
            } catch (err) {
                console.error('[WS] Failed to parse message:', err);
            }
        };

        ws.onerror = (event) => {
            console.error('[WS] Error:', event);
            const errorMsg = 'WebSocket connection error';
            setState((prev) => ({ ...prev, error: errorMsg }));
            onError?.(errorMsg);
        };

        ws.onclose = (event) => {
            console.log('[WS] Closed:', event.code, event.reason);
            setState((prev) => ({ ...prev, isConnected: false }));
            wsRef.current = null;

            // Attempt reconnect if not completed and not max attempts (5)
            if (
                !isCompleteRef.current && // Use ref for closure scope
                reconnectAttemptsRef.current < maxReconnectAttempts &&
                event.code !== 1000 // Normal closure
            ) {
                reconnectAttemptsRef.current += 1;
                const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000);
                console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current})`);

                reconnectTimeoutRef.current = setTimeout(() => {
                    setRetryTrigger(prev => prev + 1);
                }, delay);
            }
        };
    }, [runId, onComplete, onError]);

    // Reconnect when trigger changes
    useEffect(() => {
        if (retryTrigger > 0) {
            connect();
        }
    }, [retryTrigger, connect]);

    // Disconnect
    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
        if (wsRef.current) {
            wsRef.current.close(1000, 'User requested disconnect');
            wsRef.current = null;
        }
        setState(initialState);
    }, []);

    // Reset state when runId changes
    useEffect(() => {
        setTimeout(() => setState(initialState), 0);
        reconnectAttemptsRef.current = 0;
    }, [runId]);

    // Auto-connect on mount or when runId changes
    useEffect(() => {
        if (autoConnect && runId) {
            connect();
        }

        return () => {
            disconnect();
        };
    }, [runId, autoConnect, connect, disconnect]);

    return {
        ...state,
        connect,
        disconnect,
    };
}

export default useAnalysisProgress;
