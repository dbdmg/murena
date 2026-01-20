/**
 * Analysis API Endpoints
 *
 * Handles communication with the backend analysis API for running
 * AI-powered property searches and retrieving results.
 */

import { apiClient } from '../client';
import type {
    AnalysisRequest,
    AnalysisStartResponse,
    AnalysisResults,
    AgentStep,
    AgentStepsResponse,
    AnalysisHistoryItem,
} from '../types';

// API URL without base path (apiClient already has /api/v1)
const ANALYSIS_BASE = '/analysis';

export const analysisApi = {
    /**
     * Start a new analysis run.
     * Returns immediately with run_id - use WebSocket to track progress.
     *
     * @param request - Analysis parameters (query, dataset_key, limits)
     * @returns Promise with run_id and initial status
     */
    startAnalysis: async (request: AnalysisRequest): Promise<AnalysisStartResponse> => {
        const payload = {
            query: request.query,
            dataset_key: request.dataset_key ?? 'full',
            map_limit: request.map_limit ?? 500,
            llm_limit: request.llm_limit ?? 10,
            analysis_mode: request.analysis_mode ?? 'agent',
        };

        const response = await apiClient.post<AnalysisStartResponse>(
            ANALYSIS_BASE,
            payload
        );
        return response.data;
    },

    /**
     * Get results for a completed (or in-progress) analysis run.
     *
     * @param runId - The run ID returned from startAnalysis
     * @returns Full analysis results including buildings and gemini_responses
     */
    getResults: async (runId: string): Promise<AnalysisResults> => {
        const response = await apiClient.get<AnalysisResults>(
            `${ANALYSIS_BASE}/${runId}`
        );
        return response.data;
    },

    /**
     * Get agent steps for expert UI - shows prompts and responses from each agent.
     *
     * @param runId - The run ID
     * @param options - Optional filters (keys, include_prompt, include_raw)
     * @returns Array of agent steps with structured data
     */
    getAgentSteps: async (
        runId: string,
        options?: {
            keys?: string[];
            include_prompt?: boolean;
            include_raw?: boolean;
        }
    ): Promise<AgentStep[]> => {
        const params = new URLSearchParams();

        if (options?.keys?.length) {
            params.set('keys', options.keys.join(','));
        }
        if (options?.include_prompt !== undefined) {
            params.set('include_prompt', String(options.include_prompt));
        }
        if (options?.include_raw !== undefined) {
            params.set('include_raw', String(options.include_raw));
        }

        const queryString = params.toString();
        const url = queryString
            ? `${ANALYSIS_BASE}/${runId}/agent_steps?${queryString}`
            : `${ANALYSIS_BASE}/${runId}/agent_steps`;

        const response = await apiClient.get<AgentStepsResponse>(url);
        return response.data.steps;
    },

    /**
     * Get raw gemini_responses for a run (useful for debugging).
     *
     * @param runId - The run ID
     * @param keys - Optional: filter to specific keys
     * @returns Raw gemini_responses object
     */
    getGeminiResponses: async (
        runId: string,
        keys?: string[]
    ): Promise<Record<string, unknown>> => {
        const params = keys?.length ? `?keys=${keys.join(',')}` : '';
        const response = await apiClient.get<Record<string, unknown>>(
            `${ANALYSIS_BASE}/${runId}/gemini_responses${params}`
        );
        return response.data;
    },

    /**
     * Get analysis history for the current user.
     *
     * @param limit - Max number of results (default 50)
     * @param offset - Pagination offset (default 0)
     * @returns Array of past analysis runs
     */
    getHistory: async (
        limit: number = 50,
        offset: number = 0
    ): Promise<AnalysisHistoryItem[]> => {
        const response = await apiClient.get<AnalysisHistoryItem[]>(
            `${ANALYSIS_BASE}/history`,
            { params: { limit, offset } }
        );
        return response.data;
    },

    /**
     * Delete an analysis run.
     *
     * @param runId - The run ID to delete
     */
    deleteRun: async (runId: string): Promise<void> => {
        await apiClient.delete(`${ANALYSIS_BASE}/${runId}`);
    },

    /**
     * Get list of available demo runs (pre-computed analyses).
     *
     * @returns Array of demo IDs
     */
    getDemos: async (): Promise<string[]> => {
        const response = await apiClient.get<unknown>(`${ANALYSIS_BASE}/demos`);
        const data = response.data as unknown;

        if (Array.isArray(data)) {
            // Support both legacy formats:
            // - string[] (demo folder names)
            // - object[] with { demo_id: string, ... }
            const mapped = data
                .map((item) => {
                    if (typeof item === 'string') return item;
                    if (item && typeof item === 'object' && 'demo_id' in item) {
                        const demoId = (item as any).demo_id;
                        return typeof demoId === 'string' ? demoId : null;
                    }
                    return null;
                })
                .filter((x): x is string => typeof x === 'string' && x.length > 0);

            return mapped;
        }

        return [];
    },

    /**
     * Load a demo run (creates a completed run from pre-saved data).
     *
     * @param demoId - Demo folder ID
     * @param limit - Max buildings to load
     * @returns Run info like startAnalysis response
     */
    loadDemo: async (
        demoId: string,
        limit: number = 50
    ): Promise<AnalysisStartResponse> => {
        const response = await apiClient.post<AnalysisStartResponse>(
            `${ANALYSIS_BASE}/demos/${demoId}`,
            null,
            { params: { limit } }
        );
        return response.data;
    },
};

export default analysisApi;
