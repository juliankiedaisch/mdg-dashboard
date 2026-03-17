import axios from 'axios';
import socketService from './socket';

// API URL is now injected by Vite from the central .env file
const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: apiUrl,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Track if we're already redirecting to prevent multiple redirects
let isRedirecting = false;

// Add request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    console.log('API Request:', config.method.toUpperCase(), config.url);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response) {
      // Server responded with error status
      console.error('API Error Response:', error.response.status, error.response.data);
      
      if (error.response.status === 401) {
        // Only redirect to login if:
        // 1. Not already on the login page
        // 2. Not the auth status check itself (which is expected to return 401)
        // 3. Not already redirecting (prevents multiple simultaneous redirects)
        const isOnLoginPage = window.location.pathname === '/login';
        const isAuthStatusCheck = error.config?.url?.includes('/api/auth/status');
        
        if (!isOnLoginPage && !isAuthStatusCheck && !isRedirecting) {
          // Unauthorized - redirect to login
          isRedirecting = true;
          console.log('Session expired, redirecting to login...');
          
          // Disconnect socket to prevent reconnection attempts
          socketService.disconnect();
          
          window.location.href = '/login';
        }
      } else if (error.response.status === 403) {
        // Forbidden - redirect to not-allowed page
        const isOnNotAllowedPage = window.location.pathname === '/not-allowed';
        
        if (!isOnNotAllowedPage) {
          window.location.href = '/not-allowed';
        }
      }
    } else if (error.request) {
      // Request was made but no response
      console.error('API No Response:', error.request);
    } else {
      // Something else happened
      console.error('API Error:', error.message);
    }
    return Promise.reject(error);
  }
);

export default api;
