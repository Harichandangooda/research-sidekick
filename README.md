# Research Paper Sidekick

Research Paper Sidekick is a local research workflow application for discovering,
analyzing, and planning experiments around academic papers. It combines a
Streamlit interface with a FastAPI backend, an OpenAI Agents SDK coordinator,
SQLite persistence, and paper retrieval through ChromaDB and
sentence-transformers.

The project currently supports authenticated, user-isolated research sessions.
It is suitable for local development and evaluation. It has not yet been
hardened for public, multi-tenant production deployment.

## Features

- Email and password registration and login
- JWT bearer authentication
- User-owned research sessions displayed as clickable sidebar conversations
- Automatic conversation titles derived from the first research prompt
- Conversation rename and delete controls
- Persistent chat history and generated reports
- PDF upload, text extraction, and metadata storage
- Local semantic indexing and retrieval for uploaded papers
- Coordinator-driven research workflows using specialist agents:
  - Paper discovery with web search
  - Structured paper analysis
  - Experiment and reproduction planning
- Streamlit frontend backed exclusively by FastAPI endpoints
- Persistent SQLite and ChromaDB storage

## Architecture

```text
Streamlit frontend (app.py)
        |
        | HTTP + JWT bearer token
        v
FastAPI backend (backend/main.py)
        |
        +-- Authentication and authorization
        +-- Session, paper, message, and report services
        +-- OpenAI Agents SDK coordinator
        +-- RAG retrieval
        |
        +-- SQLite: users and application records
        +-- ChromaDB: persistent paper embeddings
```

The backend owns all business logic and persistence. The Streamlit application
only manages presentation, browser session state, and API requests.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- An OpenAI API key with access to the configured models and tools

The first paper upload may take longer because the
`sentence-transformers/all-MiniLM-L6-v2` model must be downloaded and loaded.

## Setup

1. Install the locked dependencies:

   ```powershell
   uv sync
   ```

2. Create a local `.env` file from `.env.example`:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Generate a JWT signing secret:

   ```powershell
   uv run python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

4. Add the generated secret and your OpenAI API key to `.env`:

   ```dotenv
   JWT_SECRET_KEY=replace-with-the-generated-secret
   JWT_ALGORITHM=HS256
   JWT_EXPIRE_MINUTES=1440
   OPENAI_API_KEY=replace-with-your-openai-api-key
   ```
   
Do not commit `.env`. It is intentionally excluded by `.gitignore`.

## Running Locally

Start the backend from the repository root:

```powershell
uv run uvicorn backend.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Useful development URLs:

- Health check: `http://127.0.0.1:8000/health`
- Interactive API documentation: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

In a second terminal, start the frontend:

```powershell
uv run streamlit run app.py
```

Streamlit normally opens at `http://localhost:8501`.

To use a backend at another address, set:

```dotenv
SIDEKICK_API_BASE_URL=http://127.0.0.1:8000
```

## Using the Application

1. Register with an email address and a password of at least eight characters.
2. Create a new conversation or select an existing one from the sidebar.
3. Optionally upload a text-based PDF and select it as the active paper.
4. Enter a research request or ask a follow-up question.
5. Review the generated answer, chat history, indexed papers, and saved reports.

New conversations initially use the title `New Research Session`. The first
research prompt replaces that placeholder with a concise title, making sessions
easy to distinguish in the sidebar. Use the pencil control beside a
conversation to rename it manually. Use the delete control to remove it after
confirmation.

Every completed coordinator response is currently saved as a report. Recent
messages from the selected session are supplied to the coordinator as context.
When a paper is selected, the five most relevant indexed chunks are also added
to the coordinator input.

## Authentication

`POST /auth/register` creates a user with a bcrypt password hash and returns a
signed access token. `POST /auth/login` verifies the password and returns the
same response shape. The Streamlit frontend stores the token in
`st.session_state` and sends it on protected calls:

```http
Authorization: Bearer <access-token>
```

The backend derives the user ID from the verified token. It does not accept a
user ID from request bodies. Session ownership is checked before message,
paper, chat, and report operations. A `401` response clears the frontend's
local authentication state.

Tokens expire after `JWT_EXPIRE_MINUTES`. Changing `JWT_SECRET_KEY` invalidates
all existing tokens.

## API Overview

Public endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Backend health check |
| `POST` | `/auth/register` | Register and receive an access token |
| `POST` | `/auth/login` | Log in and receive an access token |

Authenticated endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/auth/me` | Return the current user |
| `POST` | `/sessions` | Create a research session |
| `GET` | `/sessions` | List the current user's sessions |
| `GET` | `/sessions/{session_id}` | Get an owned session |
| `PATCH` | `/sessions/{session_id}` | Rename an owned session |
| `DELETE` | `/sessions/{session_id}` | Delete an owned session and its contents |
| `GET` | `/sessions/{session_id}/messages` | List session messages |
| `POST` | `/sessions/{session_id}/chat` | Run the coordinator |
| `POST` | `/sessions/{session_id}/papers` | Upload and index a PDF |
| `GET` | `/sessions/{session_id}/papers` | List session papers |
| `GET` | `/papers/{paper_id}` | Get owned paper metadata |
| `GET` | `/sessions/{session_id}/reports` | List session reports |
| `GET` | `/reports/{report_id}` | Get an owned report |

Example chat request:

```json
{
  "prompt": "Summarize the paper and identify its main limitations.",
  "paper_id": 1
}
```

`paper_id` is optional, but when provided it must belong to the requested
session and authenticated user.

Example session rename request:

```json
{
  "title": "JEPA architecture comparison"
}
```

Session titles must not be blank and may contain at most 80 characters.
Surrounding whitespace is removed before the title is saved.

## Persistence

Runtime data is stored locally:

- `sidekick.db` contains users, sessions, messages, paper metadata and text,
  and reports.
- `chroma_db/` contains persistent paper chunks and embeddings.

Both paths are excluded from Git. Deleting either path deletes the
corresponding local state.

Deleting a conversation through the application removes its messages, papers,
and reports through SQLite cascading relationships. ChromaDB chunks belonging
to its uploaded papers are also removed.

Database tables are initialized during FastAPI startup. On an older database,
the migration adds session ownership and assigns pre-authentication sessions
to an internal `legacy@local` user. Those sessions are preserved, but they are
not automatically transferred to a newly registered account. Reassigning
legacy data currently requires a deliberate database migration.

## Project Structure

```text
.
|-- app.py                         # Streamlit frontend and API client
|-- backend/
|   |-- main.py                    # FastAPI application and routes
|   |-- auth.py                    # Password hashing and JWT dependency
|   |-- agents/
|   |   |-- sidekick.py            # Coordinator
|   |   `-- tools.py               # Specialist agents
|   |-- schemas/
|   |   |-- request_models.py      # Pydantic request models
|   |   `-- response_models.py     # Pydantic response models
|   |-- services/
|   |   |-- auth_service.py
|   |   |-- document_parser.py
|   |   |-- paper_service.py
|   |   |-- rag_service.py
|   |   |-- report_service.py
|   |   |-- session_service.py
|   |   `-- sidekick_service.py
|   `-- storage/
|       |-- rag_store.py            # ChromaDB and embedding model
|       `-- session_store.py        # SQLite schema and queries
|-- .env.example
|-- pyproject.toml
`-- uv.lock
```

## Current Limitations

- Authentication uses access tokens only. There are no refresh tokens, OAuth
  providers, password reset flow, email verification, roles, or account
  management endpoints.
- The JWT signing secret is shared application configuration. Secret rotation
  and token revocation are not implemented.
- CORS is configured only for local Streamlit addresses on port `8501`.
- SQLite is appropriate for local use and light concurrency, not a high-write
  distributed deployment.
- Agent execution is synchronous and can occupy a backend worker for the
  duration of an OpenAI request.
- Uploaded PDFs are read into memory, and no explicit upload-size limit is
  enforced by the application.
- PDF extraction uses `pypdf`; scanned or image-only papers require OCR, which
  is not implemented.
- RAG uses fixed character-based chunks and a fixed local embedding model.
- Reports are saved for every successful coordinator response rather than
  being classified by response type.
- OpenAI model and web-search usage can incur API charges.
- Automated tests and production deployment configuration are not yet
  included.

## Development Checks

Compile the application:

```powershell
uv run python -m compileall -q app.py backend
```

Confirm that the lockfile matches `pyproject.toml`:

```powershell
uv lock --check
```

Before exposing the application beyond local development, add automated tests,
request-size limits, structured logging, rate limiting, secure HTTPS
termination, production CORS configuration, and a deliberate database backup
and migration process.
