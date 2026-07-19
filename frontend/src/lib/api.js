import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("cv_access");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const orig = err.config;
    if (err.response?.status === 401 && !orig._retry) {
      orig._retry = true;
      const rt = localStorage.getItem("cv_refresh");
      if (rt) {
        try {
          refreshing = refreshing || axios.post(`${API_BASE}/auth/refresh`, { refresh_token: rt });
          const { data } = await refreshing;
          refreshing = null;
          localStorage.setItem("cv_access", data.access_token);
          localStorage.setItem("cv_refresh", data.refresh_token);
          orig.headers.Authorization = `Bearer ${data.access_token}`;
          return api(orig);
        } catch (e) {
          refreshing = null;
          localStorage.removeItem("cv_access");
          localStorage.removeItem("cv_refresh");
        }
      }
    }
    return Promise.reject(err);
  }
);
