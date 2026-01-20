import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import type { AccessToken } from './types';

// API Configuration
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Create Axios Instance
export const apiClient: AxiosInstance = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 30000, // 30s timeout
});

// Request Interceptor: Attach Token
apiClient.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        const token = localStorage.getItem('access_token');
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error: AxiosError) => {
        return Promise.reject(error);
    }
);

// Response Interceptor: Handle Errors (401)
apiClient.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        // Check if error is 401 (Unauthorized) and we haven't retried yet
        // NOTE: Implementing full refresh logic can be complex.
        // For MVP/Phase 3, we simply logout on 401.
        if (error.response?.status === 401) {
            console.warn('Unauthorized - clearing session');
            localStorage.removeItem('access_token');
            localStorage.removeItem('user');

            // Redirect to login if not already there
            if (!window.location.pathname.includes('/login')) {
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

/**
 * Helper to set auth data after login
 */
export const setAuthSession = (tokenData: AccessToken) => {
    localStorage.setItem('access_token', tokenData.access_token);
};

export const clearAuthSession = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
};

export default apiClient;
