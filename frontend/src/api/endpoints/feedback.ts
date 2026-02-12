/**
 * API client for agent feedback endpoints
 */

import apiClient from '../client';
import type { AgentFeedbackSubmit, AgentFeedbackResponse, BuildingFeedbackSubmit } from '../types';

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

    /**
     * Submit feedback for a specific building
     */
    async submitBuildingFeedback(data: BuildingFeedbackSubmit): Promise<AgentFeedbackResponse> {
        const response = await apiClient.post<AgentFeedbackResponse>('/feedback/building', data);
        return response.data;
    },

    /**
     * Get all feedback (global, agent, and building) for a specific analysis run
     */
    async getBuildingFeedback(runId: string, buildingId: string): Promise<AgentFeedbackResponse[]> {
        const response = await apiClient.get<AgentFeedbackResponse[]>('/feedback/building', {
            params: { run_id: runId, building_id: buildingId },
        });
        return response.data;
    },

    /**
     * Get all feedback (global, agent, and building) for a specific analysis run
     */
    async getAllRunFeedback(runId: string): Promise<AgentFeedbackResponse[]> {
        const response = await apiClient.get<AgentFeedbackResponse[]>('/feedback/run/all', {
            params: { run_id: runId },
        });
        return response.data;
    },

    /**
     * Delete a feedback entry
     */
    async deleteFeedback(feedbackId: number): Promise<void> {
        await apiClient.delete(`/feedback/${feedbackId}`);
    },
};
