import apiClient from '../client';
import type { LoginRequest, RegisterRequest, AccessToken, User } from '../types';

export const authApi = {
    /**
     * Login with username and password
     * NOTE: Backend expects FormData (OAuth2 spec) for /login, NOT JSON
     */
    login: async (credentials: LoginRequest): Promise<AccessToken> => {
        // Convert JSON to FormData for OAuth2PasswordRequestForm compatibility
        const formData = new FormData();
        formData.append('username', credentials.username);
        formData.append('password', credentials.password);

        const response = await apiClient.post<AccessToken>('/auth/login', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },

    /**
     * Register a new user
     */
    register: async (data: RegisterRequest): Promise<User> => {
        const response = await apiClient.post<User>('/auth/register', data);
        return response.data;
    },

    /**
     * Get current user profile
     */
    getMe: async (): Promise<User> => {
        const response = await apiClient.get<User>('/auth/me');
        return response.data;
    },

    /**
     * Refresh token
     */
    refresh: async (): Promise<AccessToken> => {
        const response = await apiClient.post<AccessToken>('/auth/refresh');
        return response.data;
    },
};
