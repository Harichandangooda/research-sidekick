from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from backend.auth import get_current_user
from backend.limits import MAX_UPLOAD_BYTES
from backend.schemas.request_models import AuthRequest, ChatRequest, SessionUpdateRequest
from backend.schemas.response_models import (
    AuthResponse,
    ChatResponse,
    HealthResponse,
    MessageResponse,
    PaperResponse,
    PaperUploadResponse,
    ReportResponse,
    SessionResponse,
    UserResponse,
)
from backend.services import auth_service, paper_service, report_service, session_service, sidekick_service
from backend.storage.session_store import init_db

load_dotenv(override=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Research Paper Sidekick API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CurrentUser = Annotated[dict, Depends(get_current_user)]

@app.get("/")
def root():
    return {"message": "Backend is running"}


@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=AuthResponse)
def register(request: AuthRequest) -> dict:
    return auth_service.register_user(request.email, request.password)


@app.post("/auth/login", response_model=AuthResponse)
def login(request: AuthRequest) -> dict:
    return auth_service.login_user(request.email, request.password)


@app.get("/auth/me", response_model=UserResponse)
def me(current_user: CurrentUser) -> dict:
    return {"id": current_user["id"], "email": current_user["email"]}


@app.post("/sessions", response_model=SessionResponse)
def create_session(current_user: CurrentUser) -> dict:
    return session_service.create_research_session(current_user["id"])


@app.get("/sessions", response_model=list[SessionResponse])
def list_sessions(current_user: CurrentUser) -> list[dict]:
    return session_service.list_research_sessions(current_user["id"])


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, current_user: CurrentUser) -> dict:
    session = session_service.get_research_session(session_id, current_user["id"])
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.patch("/sessions/{session_id}", response_model=SessionResponse)
def rename_session(
    session_id: str, request: SessionUpdateRequest, current_user: CurrentUser
) -> dict:
    session = session_service.rename_research_session(
        session_id, current_user["id"], request.title
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, current_user: CurrentUser) -> Response:
    if not session_service.delete_research_session(session_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=204)


@app.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
def get_messages(session_id: str, current_user: CurrentUser) -> list[dict]:
    ensure_session(session_id, current_user["id"])
    return session_service.get_chat_history(session_id)


@app.post("/sessions/{session_id}/chat", response_model=ChatResponse)
def chat(session_id: str, request: ChatRequest, current_user: CurrentUser) -> dict:
    ensure_session(session_id, current_user["id"])
    if request.paper_id is not None:
        paper = paper_service.get_paper_metadata_for_user(request.paper_id, current_user["id"])
        if paper is None or paper["session_id"] != session_id:
            raise HTTPException(status_code=404, detail="Paper not found for this session")
    try:
        return sidekick_service.run_chat(session_id, request.prompt, request.paper_id, request.upload_attempted,
                                         str(request.request_id) if request.request_id else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sidekick run failed: {exc}") from exc


@app.post("/sessions/{session_id}/papers", response_model=PaperUploadResponse)
async def upload_paper(session_id: str, current_user: CurrentUser, file: UploadFile = File(...)) -> dict:
    await run_in_threadpool(ensure_session, session_id, current_user["id"])
    is_pdf = (file.filename or "").lower().endswith(".pdf")
    if file.content_type not in {"application/pdf", "application/x-pdf"} and not is_pdf:
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")
    try:
        file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="PDF uploads must be 20 MB or smaller")
        return await run_in_threadpool(paper_service.save_uploaded_pdf, session_id,
                                       file.filename or "uploaded.pdf", file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF upload failed: {exc}") from exc
    finally:
        await file.close()


@app.get("/sessions/{session_id}/papers", response_model=list[PaperResponse])
def list_papers(session_id: str, current_user: CurrentUser) -> list[dict]:
    ensure_session(session_id, current_user["id"])
    return paper_service.list_session_papers(session_id)


@app.get("/papers/{paper_id}", response_model=PaperResponse)
def get_paper(paper_id: int, current_user: CurrentUser) -> dict:
    paper = paper_service.get_paper_metadata_for_user(paper_id, current_user["id"])
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@app.get("/sessions/{session_id}/reports", response_model=list[ReportResponse])
def list_reports(session_id: str, current_user: CurrentUser) -> list[dict]:
    ensure_session(session_id, current_user["id"])
    return report_service.list_session_reports(session_id)


@app.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: int, current_user: CurrentUser) -> dict:
    report = report_service.get_saved_report_for_user(report_id, current_user["id"])
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


def ensure_session(session_id: str, user_id: int) -> None:
    if session_service.get_research_session(session_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
