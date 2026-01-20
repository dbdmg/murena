import apiClient from '../client';
import type { MapConfig, MapMarker } from '../types';

export const mapApi = {
    /**
     * Get initial map configuration
     */
    getConfig: async (): Promise<MapConfig> => {
        const response = await apiClient.get<MapConfig>('/map/config');
        return response.data;
    },

    /**
     * Get GeoJSON overlay data
     */
    getOverlay: async (type: 'municipi' | 'omi') => {
        const response = await apiClient.get(`/map/overlays/${type}`);
        return response.data;
    },

    /**
     * Get map markers
     */
    getMarkers: async (filters?: any): Promise<MapMarker[]> => {
        const response = await apiClient.get<MapMarker[]>('/map/markers', {
            params: filters,
        });
        return response.data;
    },
};
