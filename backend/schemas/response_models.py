from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: str


class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: str


class PaperResponse(BaseModel):
    id: int
    session_id: str | None = None
    file_name: str
    file_size: int
    source: str
    created_at: str
    chunk_count: int | None = None


class PaperUploadResponse(BaseModel):
    paper_id: int
    file_name: str
    file_size: int
    chunk_count: int


class ReportResponse(BaseModel):
    id: int
    session_id: str | None = None
    title: str
    content: str
    created_at: str


class ChatResponse(BaseModel):
    response: str
    report_id: int | None = None


class UserResponse(BaseModel):
    id: int
    email: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
