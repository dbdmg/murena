
import apiClient from '../client';
import type { POIResponse } from '../types';
import type { GeoJsonObject } from 'geojson';

export const layersApi = {
    /**
     * Get POIs filtered by category and bounding box
     */
    getPOIs: async (
        categories?: string[],
        bounds?: { min_lat: number; max_lat: number; min_lon: number; max_lon: number },
        limit?: number
    ): Promise<POIResponse> => {
        const params: Record<string, string | number> = {};
        if (categories && categories.length > 0) {
            params.categories = categories.join('|');
        }
        if (bounds) {
            params.min_lat = bounds.min_lat;
            params.max_lat = bounds.max_lat;
            params.min_lon = bounds.min_lon;
            params.max_lon = bounds.max_lon;
        }
        if (limit) {
            params.limit = limit;
        }

        const response = await apiClient.get<POIResponse>('/layers/pois', {
            params,
        });
        return response.data;
    },

    /**
     * Get Zone OMI GeoJSON
     */
    getZoneOMI: async (): Promise<GeoJsonObject> => {
        const response = await apiClient.get('/layers/zone-omi');
        return response.data;
    },
};
