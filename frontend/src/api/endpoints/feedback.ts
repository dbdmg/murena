/**
 * API client for agent feedback endpoints
 */

import apiClient from '../client';
import type { AgentFeedbackSubmit, AgentFeedbackResponse } from '../types';

export const feedbackApi = {
    /**
     * Submit feedback for a specific agent or global analysis
     */
    async submitAgentFeedback(data: AgentFeedbackSubmit): Promise<AgentFeedbackResponse> {
        const response = await apiClient.post<AgentFeedbackResponse>('/feedback/agent', data);
        return response.data;
    },

    /**
     * Get all agent feedback for a specific analysis run
     */
    async getAgentFeedback(runId: string): Promise<AgentFeedbackResponse[]> {
        const response = await apiClient.get<AgentFeedbackResponse[]>('/feedback/agent', {
            params: { run_id: runId },
        });
        return response.data;
    },
};
