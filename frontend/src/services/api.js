import axios from 'axios';

// Get configuration from environment variables
const API_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:5000/api';
export const API_BASE_URL = API_URL;
const API_TIMEOUT = parseInt(process.env.REACT_APP_API_TIMEOUT) || 30000;

// Token management
const TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

export const tokenManager = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  setToken: (token) => localStorage.setItem(TOKEN_KEY, token),
  getRefreshToken: () => localStorage.getItem(REFRESH_TOKEN_KEY),
  setRefreshToken: (token) => localStorage.setItem(REFRESH_TOKEN_KEY, token),
  clearTokens: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
  hasToken: () => !!localStorage.getItem(TOKEN_KEY)
};

// Create axios instance with base configuration
const api = axios.create({
  baseURL: API_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for authentication and logging
api.interceptors.request.use(
  (config) => {
    console.log(`Making ${config.method?.toUpperCase()} request to ${config.url}`);
    
    // Add auth token if available
    const token = tokenManager.getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    return config;
  },
  (error) => {
    console.error('Request error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling and token refresh
api.interceptors.response.use(
  (response) => {
    console.log(`Response from ${response.config.url}:`, response.status);
    return response;
  },
  async (error) => {
    console.error('Response error:', error);
    
    const originalRequest = error.config;
    
    // Handle 401 errors (unauthorized) - try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry && tokenManager.hasToken()) {
      originalRequest._retry = true;
      
      try {
        const refreshToken = tokenManager.getRefreshToken();
        if (refreshToken) {
          const response = await axios.post(`${API_URL}/auth/refresh`, {
            refresh_token: refreshToken
          });
          
          const { access_token } = response.data;
          tokenManager.setToken(access_token);
          
          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return axios(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, clear tokens and redirect to login
        tokenManager.clearTokens();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    
    if (error.code === 'ECONNABORTED') {
      console.error('Request timed out');
    } else if (error.response) {
      // Server responded with error status
      console.error('Server error:', error.response.status, error.response.data);
    } else if (error.request) {
      // Request was made but no response received
      console.error('No response received:', error.request);
    }
    
    return Promise.reject(error);
  }
);

// Authentication API functions
export const authAPI = {
  register: (username, email, password) => 
    api.post('/auth/register', { username, email, password }),
  
  login: (username, password) => 
    api.post('/auth/login', { username, password }),
  
  refresh: (refreshToken) => 
    api.post('/auth/refresh', { refresh_token: refreshToken }),
  
  getProfile: () => 
    api.get('/auth/profile'),
  
  updateProfile: (username, email) => 
    api.put('/auth/profile', { username, email }),
  
  changePassword: (currentPassword, newPassword) => 
    api.post('/auth/change-password', { 
      current_password: currentPassword, 
      new_password: newPassword 
    }),
  
  deleteAccount: (password) => 
    api.delete('/auth/delete-account', { data: { password } })
};

export default api;
