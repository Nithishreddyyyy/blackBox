# Project Description: BlackBox — AI Red-Team Challenge Platform

> **Purpose of this document:** This document provides a complete, structured technical overview of the **BlackBox** repository. It serves as context for LLMs, developers, and AI coding assistants working on this project.

---

## 1. Overview

**BlackBox** is a web-based competition and red-teaming platform where participants attempt to prompt-engineer or jailbreak a controlled Large Language Model (LLM) to achieve a specified target output (e.g., retrieving a secret token/flag or bypassing model guardrails).

### Core Concept & Workflow
1. **Admins** configure competition sessions, set custom system prompts, select LLM providers/models, set rate limits, broadcast real-time announcements, monitor prompt logs, and manage participants.
2. **Participants (Users)** log into a dedicated chat interface, interact with the model within configured rate/message limits, and try to make the model output the target flag (e.g., `FLAG{jailbreak_successful}`).
3. **Scoring & Leaderboard**: When a user's prompt triggers the model to output the target string, the backend automatically flags the session as completed, computes a score based on prompts used and completion speed, updates the live leaderboard, and broadcasts a WebSocket notification to admins.

---

## 2. Technology Stack

### Frontend (`/frontend`)
- **Framework**: Next.js 16 (App Router), React 19, TypeScript
- **Styling**: TailwindCSS v4 with CSS Modules & CSS variables (`globals.css`) for dark/light theme management
- **Markdown & Rendering**: `react-markdown`, `remark-gfm`, `rehype-raw`
- **State & Auth**: Custom React Context (`AuthContext` in `src/lib/auth.tsx`), Axios/Fetch API client (`src/lib/api.ts`)

### Backend (`/backend`)
- **Framework**: FastAPI (Python 3.12+)
- **Server**: Uvicorn with ASGI WebSockets support
- **Database ORM**: SQLAlchemy 2.0 with MySQL driver (`pymysql`) or SQLite fallback
- **Migrations & Compatibility**: Alembic setup + auto schema patches on app startup (`ensure_schema_compatibility`)
- **Authentication**: JWT (`python-jose`) with `bcrypt` password hashing (`passlib`)
- **Rate Limiting & Concurrency**: Custom per-minute rate limits + `asyncio.Semaphore(5)` for LLM call control
- **WebSockets**: Real-time broadcast notification & live activity manager (`WebSocketManager`)

### LLM Abstraction Layer (`backend/app/llm_provider.py`)
Provides a pluggable factory supporting three providers without core code changes:
- **Ollama**: Local LLM endpoint via HTTP POST to `/api/chat`
- **OpenAI**: Direct API integration (`gpt-4o`, `gpt-4o-mini`, etc.)
- **OpenRouter**: OpenAI-compatible client routed to `https://openrouter.ai/api/v1`

---

## 3. Directory & File Structure

```text
blackBox/
├── PRD.md                         # Product Requirements Document
├── proj_desc.md                   # Complete LLM Context Document (This file)
│
├── backend/                       # Python FastAPI Backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI entry point, lifespan, CORS, schema patches, DB seeding
│   │   ├── config.py              # Pydantic Settings (.env configuration loader)
│   │   ├── database.py            # SQLAlchemy engine & session factory
│   │   ├── models.py              # SQLAlchemy DB ORM models
│   │   ├── schemas.py             # Pydantic request/response validation schemas
│   │   ├── auth.py                # Password hashing, JWT creation & dependency injection
│   │   ├── llm_provider.py        # LLM Provider Abstraction (Ollama, OpenAI, OpenRouter)
│   │   ├── websocket_manager.py   # WebSocket connection pool & broadcasting manager
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── auth.py            # Login, register, current user info endpoints
│   │       ├── chat.py            # User prompt submission & chat history retrieval
│   │       ├── admin.py           # Admin management: stats, users, sessions, logs, settings, notify
│   │       ├── public.py          # Public leaderboard & notification endpoints
│   │       └── websocket.py       # WS endpoint for live notifications & events
│   ├── alembic_setup.py           # Database migration helper
│   ├── blackbox_backup.sql        # Database backup file
│   ├── pyproject.toml / requirements.txt # Python dependencies
│   └── .env.example               # Backend environment variable template
│
└── frontend/                      # Next.js Frontend Application
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx         # Root layout with AuthProvider & Theme Provider
    │   │   ├── page.tsx           # Home redirect page
    │   │   ├── globals.css        # Global CSS design tokens & dark theme
    │   │   ├── theme-toggle.tsx   # Light/Dark mode switcher component
    │   │   ├── login/
    │   │   │   └── page.tsx       # Dual-tab login (User / Admin)
    │   │   ├── user/
    │   │   │   ├── layout.tsx     # User layout (Header, Nav, System Announcements)
    │   │   │   ├── page.tsx       # Participant Chat Interface & Instructions
    │   │   │   ├── user.module.css
    │   │   │   ├── chat.module.css
    │   │   │   └── leaderboard/   # User view of the leaderboard
    │   │   └── admin/
    │   │       ├── layout.tsx     # Admin sidebar layout & live WS alerts
    │   │       ├── page.tsx       # Admin Dashboard (Overview & quick controls)
    │   │       ├── users/         # Manage registered participants
    │   │       ├── sessions/      # Manage competition sessions & system prompts
    │   │       ├── logs/          # Full prompt/response log viewer
    │   │       ├── notifications/ # Broadcast global announcement panel
    │   │       └── leaderboard/   # Admin leaderboard view
    │   └── lib/
    │       ├── api.ts             # Axios API client with bearer token interceptors
    │       └── auth.tsx           # Auth Context Provider (JWT storage & role check)
    ├── package.json
    ├── next.config.ts
    └── tsconfig.json
```

---

## 4. Database Schema & Data Models

| Model | Table | Key Fields | Description |
|---|---|---|---|
| `User` | `users` | `id`, `name`, `email`, `password_hash`, `role` (`admin` / `user`), `created_at` | Platform accounts |
| `Session` | `sessions` | `id`, `session_name`, `llm_system_prompts`, `start_time`, `end_time`, `status` (`pending`, `active`, `paused`, `completed`) | Challenge sessions with custom prompts |
| `UserSession` | `user_sessions` | `id`, `user_id`, `session_id`, `joined_at`, `completed_at`, `score`, `achieved_target`, `prompt_count` | Participant progress & score per session |
| `Message` | `messages` | `id`, `user_id`, `session_id`, `prompt_text`, `response_text`, `prompt_timestamp`, `response_timestamp`, `latency_ms`, `success` | Complete log of all user prompts and LLM responses |
| `AdminSettings` | `admin_settings` | `id`, `max_messages_per_user`, `max_messages_per_minute`, `challenge_duration`, `llm_provider`, `llm_model`, `leaderboard_enabled` | Dynamic global system configuration |
| `Notification` | `notifications` | `id`, `message`, `priority` (`low`, `normal`, `high`, `urgent`), `created_by`, `created_at` | Global broadcast notifications from admins |
| `AuditLog` | `audit_logs` | `id`, `actor_id`, `action_type`, `action_data`, `created_at` | Audit trail for admin actions |

---

## 5. API Endpoint Summary

### Auth Routes (`/auth`)
- `POST /auth/login` - Authenticate user/admin, returns JWT access token.
- `POST /auth/register` - User self-registration.
- `GET /auth/me` - Fetch currently authenticated user info.

### Chat Routes (`/chat`)
- `POST /chat/send` - Submit a prompt to active session LLM. Checks rate limits, logs message, checks target output match, updates score if solved.
- `GET /chat/history?session_id={id}` - Retrieve current user's message history and remaining prompt count for session.

### Admin Routes (`/admin`)
- `GET /admin/stats` - Session metrics (active users, prompt totals, target completion count).
- `GET /admin/users` & `POST /admin/users` - User account management.
- `GET /admin/sessions` & `POST /admin/sessions` - Challenge session creation & status toggle.
- `GET /admin/settings` & `POST /admin/settings` - Update rate limits, active LLM provider (`ollama` / `openai` / `openrouter`), and model name.
- `POST /admin/notify` - Send global broadcast notification to connected clients over WebSocket.
- `GET /admin/logs` - Fetch all prompt/response logs across all users for analysis.
- `GET /admin/leaderboard` - Fetch detailed competition leaderboard rankings.

### Public & WebSocket Routes (`/public`, `/ws`)
- `GET /public/leaderboard` - Public leaderboard.
- `GET /public/notifications` - Public list of recent announcements.
- `WS /ws` - WebSocket endpoint for real-time notifications and system event broadcasts.

---

## 6. Key Features & Business Logic

1. **Jailbreak Detection & Scoring Formula**:
   - On every `/chat/send`, the backend checks if `settings.TARGET_OUTPUT` (case-insensitive) is present in the LLM response.
   - If detected: `user_session.achieved_target = True`, `completed_at = datetime.utcnow()`.
   - Score calculated as: `score = round(1000 / (prompt_count + time_in_minutes), 2)` (Higher score is better; rewards fewer prompts and faster time).

2. **Rate Limiting & Guardrails**:
   - **Per-user prompt ceiling**: Configured via `max_messages_per_user`.
   - **Per-minute throttling**: Configured via `max_messages_per_minute`.
   - **Concurrency limit**: Max 5 concurrent async LLM invocations via `asyncio.Semaphore(5)` to protect local LLM instances.

3. **Dynamic Provider Switching**:
   - Admins can update the `llm_provider` and `llm_model` directly from the admin panel without restarting the backend server.

4. **Real-time WebSockets**:
   - Real-time notification banners broadcast instantly to active participant chat sessions when admins post announcements or when a user successfully jailbreaks the model.

---

## 7. How to Run the Project

### Environment Setup

#### Backend (`/backend/.env`):
```env
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/blackbox
JWT_SECRET_KEY=super-secret-jwt-key-change-this
LLM_PROVIDER=ollama # or openai, openrouter
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4o
TARGET_OUTPUT=FLAG{jailbreak_successful}
ADMIN_EMAIL=admin@blackbox.local
ADMIN_PASSWORD=adminpassword
```

#### Running Backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Running Frontend:
```bash
cd frontend
npm install
npm run dev
```
The frontend will run on `http://localhost:3000` and proxy requests to `http://localhost:8000`.
