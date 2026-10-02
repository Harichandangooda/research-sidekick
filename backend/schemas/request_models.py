from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from uuid import UUID

from backend.limits import MAX_PROMPT_CHARACTERS


class ChatRequest(BaseModel):
    prompt: str = Field(default="", max_length=MAX_PROMPT_CHARACTERS)
    paper_id: int | None = None
    upload_attempted: bool = False
    request_id: UUID | None = None


class SessionUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=80)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Title must not be blank")
        return title


class AuthRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
