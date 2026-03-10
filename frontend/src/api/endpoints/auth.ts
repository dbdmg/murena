import apiClient from '../client';
import type { LoginRequest, RegisterRequest, AccessToken, User } from '../types';

export const authApi = {
    /**
     * Login with username and password
     * NOTE: Backend expects FormData (OAuth2 spec) for /login, NOT JSON
     */
    login: async (credentials: LoginRequest): Promise<AccessToken> => {
        // Use URLSearchParams for application/x-www-form-urlencoded, standard for OAuth2 password grant
        const params = new URLSearchParams();
        params.append('username', credentials.username);
        params.append('password', credentials.password);
        params.append('grant_type', 'password');

        const response = await apiClient.post<AccessToken>('/auth/login', params, {
            headers: {
                // Ensure we override the default application/json
                'Content-Type': 'application/x-www-form-urlencoded',
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
