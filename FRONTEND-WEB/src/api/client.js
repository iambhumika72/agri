import axios from 'axios';

/**
 * Configured Axios instance for all API calls.
 * BASE_URL is read from the VITE_API_BASE_URL environment variable.
 * In development the Vite proxy forwards /api → BASE_URL.
 */
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

import { getLocationPayload } from '../utils/location';

// Request interceptor — attach auth token if present
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  
  // Attach location to POST/PATCH requests
  if (['post', 'patch'].includes(config.method?.toLowerCase())) {
    const loc = getLocationPayload();
    if (Object.keys(loc).length > 0) {
      config.data = { ...config.data, ...loc };
    }
  }
  
  return config;
});

// Response interceptor — normalize errors
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An unexpected error occurred';
    return Promise.reject(new Error(message));
  }
);

export default client;
