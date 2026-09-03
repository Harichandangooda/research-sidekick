# Research Paper Sidekick

Research Paper Sidekick is a local research workspace for discovering, analyzing,
and planning experiments around academic papers. It combines a React and
Bootstrap frontend with a FastAPI backend, an OpenAI Agents SDK coordinator,
SQLite persistence, and semantic paper retrieval through ChromaDB and
sentence-transformers.

The application supports authenticated, user-isolated research sessions. It is
intended for local development and evaluation and has not yet been hardened for
public, multi-tenant production deployment.

## Features

- React and Bootstrap user interface
- Email/password registration and login with JWT bearer authentication
- Authentication restoration on browser reload and clean expired-token handling
- User-owned research sessions with create, select, rename, and delete controls
- Automatic conversation titles derived from the first research prompt
- Persistent conversation history and generated reports
- PDF validation, upload, text extraction, indexing, and active-paper selection
- Research requests with or without a selected paper
- Answer, Papers, Reports, and Chat workspace tabs
- Responsive sidebar, loading indicators, empty states, and API error feedback
- Coordinator workflows for paper discovery, paper analysis, and experiment planning
- SQLite records and ChromaDB embeddings persisted locally

## Architecture

```text
React frontend (frontend/research-sidekick)
        |
        | Axios + JWT bearer token
        v
FastAPI backend (backend/main.py)
        |
        +-- Authentication and authorization
        +-- Session, paper, message, and report services
        +-- OpenAI Agents SDK coordinator
        +-- Retrieval-augmented generation
        |
        +-- SQLite: users and application records
        +-- ChromaDB: paper chunks and embeddings
```

The backend owns authentication, authorization, research execution, persistence,
and retrieval logic. React manages presentation and browser state and communicates
with FastAPI through a small Axios service layer.

The root-level `app.py` is the earlier Streamlit client. It remains in the
repository for reference, but the React application is the primary frontend.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- An OpenAI API key with access to the configured models and tools

The first paper upload can take longer because the
`sentence-transformers/all-MiniLM-L6-v2` model may need to be downloaded and
loaded.

## Backend Setup

1. Install the locked Python dependencies from the repository root:

   ```powershell
   uv sync
   ```

2. Create a local `.env` file and configure the required secrets:

   ```dotenv
   JWT_SECRET_KEY=replace-with-a-long-random-secret
   JWT_ALGORITHM=HS256
   JWT_EXPIRE_MINUTES=1440
   OPENAI_API_KEY=replace-with-your-openai-api-key
   ```

   A signing secret can be generated with:

   ```powershell
   uv run python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

Do not commit `.env`; it is excluded by `.gitignore`.

## Frontend Setup

Install the React dependencies:

```powershell
cd frontend/research-sidekick
npm install
```

The frontend uses `http://localhost:8000` by default. To use another FastAPI
address, create `frontend/research-sidekick/.env.local`:

```dotenv
REACT_APP_API_BASE_URL=http://127.0.0.1:8000
```

Restart the React development server after changing this variable.

## Running Locally

Start FastAPI from the repository root:

```powershell
uv run uvicorn backend.main:app --reload
```

The backend is available at `http://127.0.0.1:8000`:

- Health check: `http://127.0.0.1:8000/health`
- Interactive documentation: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

In a second terminal, start React:

```powershell
cd frontend/research-sidekick
npm start
```

The application opens at `http://localhost:3000`. FastAPI CORS accepts both
`localhost:3000` and `127.0.0.1:3000` for local development.

## Using the Application

1. Register with a valid email address and a password of at least eight characters.
2. Create a conversation or select an existing conversation from the sidebar.
3. Optionally upload a text-based PDF and select it as the active paper.
4. Enter a research request and run Sidekick.
5. Review the answer, continue the conversation, and inspect indexed papers and reports.

New conversations begin with the title `New Research Session`. The first prompt
automatically replaces that placeholder with a concise title. Every successful
coordinator response is saved as a report. Recent messages are supplied to the
coordinator as conversation context, and a selected paper contributes its five
most relevant indexed chunks.

## Authentication and Authorization

Registration and login return an access token and authenticated user. React stores
the token in browser local storage, and an Axios request interceptor adds it to
protected requests:

```http
Authorization: Bearer <access-token>
```

On reload, React validates the stored token through `GET /auth/me`. A `401`
response clears invalid or expired authentication state and returns the user to
the authentication screen.

FastAPI derives the user identity exclusively from the verified token. Session
ownership is checked before session, message, paper, chat, and report operations;
the frontend never sends a user ID to select protected data.

## API Overview

Public endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Check backend health |
| `POST` | `/auth/register` | Register and receive an access token |
| `POST` | `/auth/login` | Log in and receive an access token |

Authenticated endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/auth/me` | Return the authenticated user |
| `POST` | `/sessions` | Create a research session |
| `GET` | `/sessions` | List the user's sessions |
| `GET` | `/sessions/{session_id}` | Get an owned session |
| `PATCH` | `/sessions/{session_id}` | Rename an owned session |
| `DELETE` | `/sessions/{session_id}` | Delete an owned session and its contents |
| `GET` | `/sessions/{session_id}/messages` | List conversation messages |
| `POST` | `/sessions/{session_id}/chat` | Run the research coordinator |
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

`paper_id` may be `null`, but a supplied ID must belong to the requested session
and authenticated user.

## Persistence

- `sidekick.db` contains users, sessions, messages, paper metadata/text, and reports.
- `chroma_db/` contains persistent paper chunks and embeddings.

Both paths are excluded from Git. Deleting a conversation through the application
removes its relational records through SQLite cascading relationships and removes
the corresponding ChromaDB index.

## Project Structure

```text
.
|-- app.py                              # Legacy Streamlit client
|-- backend/
|   |-- main.py                         # FastAPI routes and application
|   |-- auth.py                         # Password hashing and JWT dependency
|   |-- agents/                         # Coordinator and specialist agents
|   |-- schemas/                        # Pydantic request/response models
|   |-- services/                       # Application service layer
|   `-- storage/                        # SQLite and ChromaDB access
|-- frontend/research-sidekick/
|   |-- public/
|   |-- src/
|   |   |-- api.js                      # Axios client and interceptors
|   |   |-- services/                   # Frontend API service functions
|   |   |-- pages/                      # Authentication and workspace pages
|   |   `-- App.js                      # Authentication lifecycle
|   |-- package.json
|   `-- package-lock.json
|-- pyproject.toml
`-- uv.lock
```

## Development Checks

Run the React tests and production build:

```powershell
cd frontend/research-sidekick
npm test -- --watchAll=false
npm run build
```

Validate the Python source and dependency lockfile from the repository root:

```powershell
uv run python -m compileall -q backend
uv lock --check
```

## Current Limitations

- Authentication uses access tokens only; refresh tokens, OAuth, password reset,
  email verification, roles, and account management are not implemented.
- SQLite is intended for local use and light concurrency.
- Agent execution is synchronous and can occupy a backend worker for the duration
  of an OpenAI request.
- Uploaded PDFs are read into memory and do not have an explicit application-level
  size limit.
- Scanned or image-only PDFs require OCR, which is not implemented.
- Reports are saved for every successful coordinator response.
- Paper and report deletion endpoints are not currently available.
- OpenAI model and web-search usage can incur API charges.
- Production deployment, rate limiting, structured logging, HTTPS termination,
  backup automation, and a formal migration workflow are not yet configured.
