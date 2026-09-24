import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
export const TOKEN_KEY = "bf_token";

const api = axios.create({ baseURL: API_BASE_URL, headers: { "Content-Type": "application/json" } });

// Attach the login token to every request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// If the server says the token is invalid/expired, sign out everywhere.
let onUnauthorized = null;
export const setUnauthorizedHandler = (fn) => (onUnauthorized = fn);
api.interceptors.response.use(
  (r) => r,
  (err) => {
    const url = err.config?.url || "";
    if (err.response?.status === 401 && !url.startsWith("/auth/login") && !url.startsWith("/auth/signup") && !url.startsWith("/auth/google")) {
      onUnauthorized?.();
    }
    return Promise.reject(err);
  }
);

export const errorMessage = (err, fallback = "Something went wrong. Please try again.") => {
  if (!err.response) return "Could not reach the AI BugFixer backend. Make sure the FastAPI server is running on port 8000.";
  const d = err.response.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg).join(", ");
  return fallback;
};

// ---- auth ----
export const getAuthConfig = () => api.get("/auth/config").then((r) => r.data);
export const signup = (body) => api.post("/auth/signup", body).then((r) => r.data);
export const login = (body) => api.post("/auth/login", body).then((r) => r.data);
export const googleLogin = (credential) => api.post("/auth/google", { credential }).then((r) => r.data);
export const fetchMe = () => api.get("/auth/me").then((r) => r.data);
export const updateProfile = (body) => api.put("/auth/me", body).then((r) => r.data);
export const uploadAvatar = (file) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post("/auth/avatar", fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
};
export const removeAvatar = () => api.delete("/auth/avatar").then((r) => r.data);
export const changePassword = (body) => api.post("/auth/change-password", body).then((r) => r.data);
export const deleteAccount = (confirm_email) => api.delete("/auth/me", { data: { confirm_email } }).then((r) => r.data);

// ---- debugging ----
export async function analyzeBug({ language, code, error, stackTrace }) {
  const r = await api.post("/analyze", { language, code, error, stack_trace: stackTrace || "" });
  return r.data;
}
export const extractTextFromImage = (file) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post("/ocr", fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
};

// ---- history ----
export const fetchHistory = (limit = 50) => api.get(`/history?limit=${limit}`).then((r) => r.data);
export const deleteHistoryItem = (id) => api.delete(`/history/${id}`).then((r) => r.data);
export const clearHistory = () => api.delete("/history").then((r) => r.data);

// ---- notifications ----
export const fetchNotifications = () => api.get("/notifications").then((r) => r.data);
export const markAllRead = () => api.post("/notifications/read-all").then((r) => r.data);
export const clearNotifications = () => api.delete("/notifications").then((r) => r.data);

// ---- practice ----
export const fetchPracticeLanguages = () => api.get("/practice/languages").then((r) => r.data);
export const fetchProblems = () => api.get("/practice/problems").then((r) => r.data);
export const fetchProblem = (id, language) => api.get(`/practice/problems/${id}`, { params: { language } }).then((r) => r.data);
export const runPractice = (body) => api.post("/practice/run", body).then((r) => r.data);
export const submitPractice = (body) => api.post("/practice/submit", body).then((r) => r.data);

export default api;
