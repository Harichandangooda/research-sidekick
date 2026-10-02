import api from "../api";

export const listSessions = () => api.get("/sessions").then(({ data }) => data);
export const createSession = () => api.post("/sessions").then(({ data }) => data);
export const renameSession = (sessionId, title) => api.patch(`/sessions/${sessionId}`, { title }).then(({ data }) => data);
export const deleteSession = (sessionId) => api.delete(`/sessions/${sessionId}`);
export const listMessages = (sessionId) => api.get(`/sessions/${sessionId}/messages`).then(({ data }) => data);
export const sendChat = (sessionId, prompt, paperId = null, uploadAttempted = false, requestId = null) => api.post(`/sessions/${sessionId}/chat`, { prompt, paper_id: paperId, upload_attempted: uploadAttempted, request_id: requestId }).then(({ data }) => data);
export const listPapers = (sessionId) => api.get(`/sessions/${sessionId}/papers`).then(({ data }) => data);
export const uploadPaper = (sessionId, file) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post(`/sessions/${sessionId}/papers`, formData).then(({ data }) => data);
};
export const listReports = (sessionId) => api.get(`/sessions/${sessionId}/reports`).then(({ data }) => data);
export const getReport = (reportId) => api.get(`/reports/${reportId}`).then(({ data }) => data);
