/**
 * useAnalysis Hook
 *
 * High-level hook that combines the Analysis API with WebSocket progress.
 * Provides a complete interface for starting analyses and tracking their progress.
 *
 * Usage:
 *   const {
 *     startAnalysis,
 *     results,
 *     progress,
 *     status,
 *     error,
 *   } = useAnalysis();
 *
 *   // Start a search
 *   await startAnalysis({ query: "Appartamenti vicino a Piazza Castello" });
 *
 *   // Track progress with progress.percent, progress.steps
 *   // Access results when status === 'completed'
 */

import { useState, useCallback } from 'react';
import { analysisApi } from '../api/endpoints/analysis';
import { useAnalysisProgress, type AnalysisProgressState } from './useAnalysisProgress';
import type {
    AnalysisRequest,
    AnalysisResults,
    AnalysisStatusType,
} from '../api/types';

export type AnalysisHookStatus = 'idle' | 'starting' | 'processing' | 'completed' | 'failed';

export interface UseAnalysisState {
    /** Current hook status */
    status: AnalysisHookStatus;
    /** Current run ID (if any) */
    runId: string | null;
    /** Analysis results (available when completed) */
    results: AnalysisResults | null;
    /** Progress state from WebSocket */
    progress: AnalysisProgressState;
    /** Error message (if any) */
    error: string | null;
    /** Whether an analysis is in progress */
    isLoading: boolean;
}

export interface UseAnalysisReturn extends UseAnalysisState {
    /** Start a new analysis */
    startAnalysis: (request: AnalysisRequest) => Promise<string>;
    /** Reset to initial state */
    reset: () => void;
    /** Load results for an existing run */
    loadResults: (runId: string) => Promise<AnalysisResults>;
    /** Load a demo run */
    loadDemo: (demoId: string) => Promise<string>;
}

const initialProgress: AnalysisProgressState = {
    percent: 0,
    step: '',
    steps: [],
    message: '',
    isConnected: false,
    isComplete: false,
    resultsUrl: null,
    error: null,
};

export function useAnalysis(): UseAnalysisReturn {
    const [status, setStatus] = useState<AnalysisHookStatus>('idle');
    const [runId, setRunId] = useState<string | null>(null);
    const [results, setResults] = useState<AnalysisResults | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Connect to WebSocket for progress when we have a runId
    const progressState = useAnalysisProgress(runId, {
        autoConnect: true,
        onComplete: async () => {

            try {
                if (runId) {
                    const analysisResults = await analysisApi.getResults(runId);
                    setResults(analysisResults);
                    setStatus('completed');
                }
            } catch (err) {
                console.error('[useAnalysis] Failed to fetch results:', err);
                setError('Failed to fetch analysis results');
                setStatus('failed');
            }
        },
        onError: (wsError) => {
            console.warn('[useAnalysis] WebSocket error:', wsError);
            // Don't fail the whole thing on WS error - we can poll instead
        },
    });

    // Start a new analysis
    const startAnalysis = useCallback(async (request: AnalysisRequest): Promise<string> => {
        setStatus('starting');
        setError(null);
        setResults(null);

        try {

            const response = await analysisApi.startAnalysis(request);

            setRunId(response.run_id);
            setStatus('processing');


            return response.run_id;
        } catch (err) {
            console.error('[useAnalysis] Failed to start analysis:', err);
            const errMsg = err instanceof Error ? err.message : 'Failed to start analysis';
            setError(errMsg);
            setStatus('failed');
            throw err;
        }
    }, []);

    // Load results for an existing run (e.g., from history)
    const loadResults = useCallback(async (existingRunId: string): Promise<AnalysisResults> => {
        setStatus('starting');
        setError(null);

        try {
            const analysisResults = await analysisApi.getResults(existingRunId);
            setRunId(existingRunId);
            setResults(analysisResults);

            // Map backend status to hook status
            const backendStatus: AnalysisStatusType = analysisResults.status;
            if (backendStatus === 'completed') {
                setStatus('completed');
            } else if (backendStatus === 'failed') {
                setStatus('failed');
            } else if (backendStatus === 'processing') {
                setStatus('processing');
            } else {
                setStatus('processing');
            }

            return analysisResults;
        } catch (err) {
            console.error('[useAnalysis] Failed to load results:', err);
            const errMsg = err instanceof Error ? err.message : 'Failed to load results';
            setError(errMsg);
            setStatus('failed');
            throw err;
        }
    }, []);

    // Load a demo run
    const loadDemo = useCallback(async (demoId: string): Promise<string> => {
        setStatus('starting');
        setError(null);
        setResults(null);

        try {

            const response = await analysisApi.loadDemo(demoId);

            setRunId(response.run_id);

            // Demo runs now return 'processing' status and simulate progress
            // The ProcessingPage will handle the WebSocket updates
            if (response.status === 'processing') {
                setStatus('processing');
            } else {
                // Fallback for old behavior or immediate completion
                const analysisResults = await analysisApi.getResults(response.run_id);
                setResults(analysisResults);
                setStatus('completed');
            }


            return response.run_id;
        } catch (err) {
            console.error('[useAnalysis] Failed to load demo:', err);
            const errMsg = err instanceof Error ? err.message : 'Failed to load demo';
            setError(errMsg);
            setStatus('failed');
            throw err;
        }
    }, []);

    // Reset to initial state
    const reset = useCallback(() => {
        setStatus('idle');
        setRunId(null);
        setResults(null);
        setError(null);
    }, []);

    // Derive isLoading from status
    const isLoading = status === 'starting' || status === 'processing';

    return {
        status,
        runId,
        results,
        progress: runId ? progressState : initialProgress,
        error,
        isLoading,
        startAnalysis,
        reset,
        loadResults,
        loadDemo,
    };
}

export default useAnalysis;
