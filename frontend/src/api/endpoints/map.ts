import apiClient from '../client';
import type { MapConfig, MapMarker, MapMarkerLite } from '../types';
import type { GeoJsonObject } from 'geojson';

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
    getOverlay: async (type: 'municipi' | 'omi'): Promise<GeoJsonObject> => {
        const response = await apiClient.get(`/map/overlays/${type}`);
        return response.data;
    },

    /**
     * Get map markers
     */
    getMarkers: async (filters?: Record<string, unknown>): Promise<MapMarker[]> => {
        const response = await apiClient.get<MapMarker[]>('/map/markers', {
            params: filters,
        });
        return response.data;
    },

    /**
     * Get lightweight map markers for background
     */
    getMarkersLite: async (filters?: Record<string, unknown>): Promise<MapMarkerLite[]> => {
        const response = await apiClient.get<MapMarkerLite[]>('/map/markers-lite', {
            params: filters,
        });
        return response.data;
    },
};
