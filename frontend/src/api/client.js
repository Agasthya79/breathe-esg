import axios from 'axios';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${BASE}/api`,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-refresh on 401
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config;
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refresh = localStorage.getItem('refresh_token');
      if (refresh) {
        try {
          const { data } = await axios.post(`${BASE}/api/auth/token/refresh/`, { refresh });
          localStorage.setItem('access_token', data.access);
          original.headers.Authorization = `Bearer ${data.access}`;
          return api(original);
        } catch {
          localStorage.clear();
          window.location.href = '/login';
        }
      } else {
        localStorage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

// Auth
export const login = (username, password) =>
  api.post('/auth/token/', { username, password });

// Clients
export const getClients = () => api.get('/clients/');

// Batches
export const getBatches = (params) => api.get('/batches/', { params });
export const uploadFile = (formData) =>
  api.post('/batches/', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

// Activities
export const getActivities = (params) => api.get('/activities/', { params });
export const getSummary = (params) => api.get('/activities/summary/', { params });
export const approveActivity = (id) => api.post(`/activities/${id}/approve/`);
export const rejectActivity = (id, note) => api.post(`/activities/${id}/reject/`, { note });
export const unlockActivity = (id, note) => api.post(`/activities/${id}/unlock/`, { note });
export const getHistory = (id) => api.get(`/activities/${id}/history/`);
export const updateActivity = (id, data) => api.patch(`/activities/${id}/`, data);

export default api;
