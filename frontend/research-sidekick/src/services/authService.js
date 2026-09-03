import api from "../api";

export const login = (credentials) => api.post("/auth/login", credentials).then(({ data }) => data);
export const register = (credentials) => api.post("/auth/register", credentials).then(({ data }) => data);
export const getCurrentUser = () => api.get("/auth/me").then(({ data }) => data);
