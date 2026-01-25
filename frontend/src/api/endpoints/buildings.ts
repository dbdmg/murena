
import client from '../client';
import type { BuildingResponse, BuildingsListResponse } from '../types';

export const buildingsApi = {
    getBuilding: async (id: string, datasetKey = 'full') => {
        const response = await client.get<BuildingResponse>(`/buildings/${id}`, {
            params: { dataset_key: datasetKey }
        });
        return response.data;
    },

    listBuildings: async (params: Record<string, unknown>) => {
        const response = await client.get<BuildingsListResponse>('/buildings', {
            params
        });
        return response.data;
    }
};
