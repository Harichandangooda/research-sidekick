import axios from "axios";

const TOKEN_KEY = "research_sidekick_token";
const api = axios.create({ baseURL: process.env.REACT_APP_API_BASE_URL || "http://localhost:8000" });

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export function setToken(token) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
}

api.interceptors.request.use((config) => {
    const token = getToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
});

let authenticationFailureHandler = null;
export function onAuthenticationFailure(handler) { authenticationFailureHandler = handler; }

api.interceptors.response.use((response) => response, (error) => {
    if (error.response?.status === 401 && getToken()) {
        setToken(null);
        authenticationFailureHandler?.();
    }
    return Promise.reject(error);
});

export function getApiError(error, fallback = "Something went wrong. Please try again.") {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join("; ") || fallback;
    if (!error.response) return "Unable to reach the server. Check that the backend is running.";
    return fallback;
}

export default api;
