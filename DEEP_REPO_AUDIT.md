# DEEP REPO AUDIT: BlackBox AI Challenge Platform

## 1. Executive Summary

- **Project Overview:** The codebase is a web-based competitive AI Red-Team platform where users interact with LLMs to bypass constraints. Administrators monitor usage, configure LLM endpoints, and determine winners. 
- **Overall Quality Rating:** 4.5 / 10. The foundation exists and recent updates introduced an `asyncio.Semaphore` for load-shedding, but the codebase still suffers from fundamental anti-patterns in asynchronous programming and database interaction.
- **Overall Scalability Rating:** 2 / 10. The backend is severely throttled due to blocking event loops, connection pool exhaustion, and missing database indexes.
- **Production-Ready:** **NO.** 
- **Concurrency Support (25–30 Users):** **NO.** If 25-30 users simultaneously query the LLM API, the FastAPI application will become unresponsive, WebSocket connections will drop, and users will face timeouts.
- **Biggest Risks:** 
  1. Complete event-loop starvation due to synchronous code in `async def` endpoints, which was *not* fixed by the recent Semaphore addition.
  2. Database Connection Pool Exhaustion (connections held during long LLM API calls).
  3. Server crash under load due to O(N) operations in database polling.
- **Top 10 Most Critical Issues:**
  1. Synchronous OpenAI/OpenRouter HTTP calls in `async def` event loops block all other requests.
  2. The newly added `asyncio.Semaphore(5)` limits concurrent requests but does not prevent the synchronous OpenAI client from freezing the main thread.
  3. Synchronous SQLAlchemy queries inside `async def` endpoints block the event loop.
  4. Database connection is held open during long-running LLM generation.
  5. Missing DB indexes on heavily queried columns (`prompt_timestamp`, composite user/session IDs).
  6. N+1 query issue in admin leaderboard and participants endpoints.
  7. Rate limits are evaluated using heavy `COUNT()` table scans rather than Redis or in-memory tracking.
  8. Websocket `user_id` type mismatch (`str` vs `int`) preventing targeted messaging and hindering cleanup.
  9. JWT token stored insecurely in frontend `localStorage` (XSS vulnerability).
  10. Redundant 10-second API polling for frontend notifications despite having an active WebSocket.

---

## 2. Repository Overview

- **Project Purpose:** An AI sandbox platform for competitions where users prompt an LLM to reveal a hidden secret.
- **Tech Stack:** Next.js (React), TailwindCSS, FastAPI, SQLAlchemy, MySQL, PyMySQL, Ollama/OpenAI APIs.
- **Folder Structure:** 
  - `/backend`: FastAPI Python app with SQLAlchemy models and local/remote LLM integrations.
  - `/frontend`: Next.js React client with user and admin dashboards.
- **Important Entry Points:** `backend/app/main.py`, `frontend/src/app/page.tsx`.

### Architecture Diagram
```text
  Client (Browser / React)
     |    |
   REST   WebSocket
     |    |
   FastAPI (Uvicorn Worker)
      |         |
SQLAlchemy    LLM_Provider (OpenAI / OpenRouter / Ollama)
      |
  MySQL DB
```

### Request Flow (Chat)
```text
Client -> POST /chat/send -> FastAPI -> DB Check Session -> DB Check Rate Limit -> Call LLM Provider -> DB Save Message -> Broadcast target_achieved (if won) -> Response to Client
```

---

## 3. Architecture Audit

### The Disconnect Between Async and Synchronous Paths
FastAPI uses an `asyncio` event loop. If non-async I/O (like a synchronous database query or `requests.get`) is executed in an `async def` function, the entire worker thread freezes. 
Currently, the architecture mixes `async def` endpoints with synchronous PyMySQL and synchronous OpenAI SDKs. This is an anti-pattern. 

### Issue: Event Loop Blocking via Synchronous LLM Calls (Unresolved)
- **Severity:** Critical
- **Files:** `backend/app/llm_provider.py`
- **Problem:** `OpenAIProvider.chat` and `OpenRouterProvider.chat` are defined as `async def chat`, but their body calls `self.client.chat.completions.create(…)` synchronously. The recent addition of `asyncio.Semaphore(5)` to limit concurrency **does not solve this**. The event loop executing one of those 5 allowed queries will stall entirely until the synchronous HTTP call finishes.
- **Impact:** Each OpenAI call takes 1-5 seconds. During this entire period, the FastAPI thread is literally frozen. If only 1 worker is running, a single prompt prevents all other users from querying, viewing stats, or keeping their WebSocket alive.
- **Fix:** Replace synchronous `OpenAI` initialization with `AsyncOpenAI` from the Python SDK, and `await` the completions call (`await self.client.chat.completions.create(...)`).

### Issue: Asynchronous Endpoints with Synchronous Database Connections
- **Severity:** Critical
- **Files:** `backend/app/routes/chat.py`, `backend/app/routes/admin.py`, `backend/app/database.py`
- **Problem:** Endpoints like `@router.post("/send")` are defined as `async def`. However, they rely on a synchronous DB connection (`SessionLocal` backed by `pymysql`).
- **Impact:** Any `db.query()` call blocks the underlying thread.
- **Fix:** Upgrade to asynchronous SQLAlchemy (`ext.asyncio` with `aiomysql`/`asyncmy` engine). Because you use an `async` LLM generator, you MUST use `ext.asyncio` with `async def` endpoints.

### Issue: Holding DB Connection During External LLM Call
- **Severity:** High
- **Files:** `backend/app/routes/chat.py`
- **Problem:** `db: DBSession = Depends(get_db)` opens a connection at the start of `/chat/send` and holds it until the endpoint returns. Between starting and finishing, the code awaits `generate_response()` which takes seconds.
- **Impact:** Since the pool size is 20 + 10 overflow, running 30 concurrent users completely exhausts the database connection pool. Any other requests during that time will instantly throw connection timeout blocks.
- **Fix:** Fetch configuration variables from the DB, explicitly commit, and return the session to the pool (`db.close()`) *before* calling the LLM. Open a new DB transaction *after* the LLM returns to log the response.

---

## 4. Frontend Audit

### Issue: Insecure JWT Storage
- **Severity:** High
- **File:** `frontend/src/lib/api.ts`
- **Problem:** The token is kept in `localStorage`. 
- **Impact:** Any XSS vulnerability allows complete account takeover.
- **Fix:** Set the JWT in an `HttpOnly`, `Secure` cookie issued by the backend instead of storing it on the client.

### Issue: Redundant Notification Polling
- **Severity:** Low
- **File:** `frontend/src/app/user/page.tsx`
- **Problem:** On line 115, `setInterval(fetchNotifs, 10_000)` fires every 10 seconds. Meanwhile, a WebSocket connection is actively listening to `"type": "notification"` events.
- **Impact:** Unnecessary requests (3 per second across 30 users) slowing down an already strained backend.
- **Fix:** Remove the `setInterval` block entirely and rely exclusively on the WebSocket handler.

### Issue: Missing Timeout/Error Fallback on Chat SEND
- **Severity:** Medium
- **File:** `frontend/src/app/user/page.tsx`
- **Problem:** The LLM request `apiFetch('/chat/send')` disables the chat bar indefinitely until a response returns. 
- **Impact:** If the backend times out without sending a proper HTTP response code, the UI stays permanently locked until the user refreshes.
- **Fix:** Add an internal timeout on the `fetch` request using `AbortController` and reset UI state if max duration (e.g., 30s) is hit.

### Issue: Theme Toggle Component Styling
- **Severity:** Low
- **File:** `frontend/src/app/theme-toggle.tsx`
- **Problem:** The new theme toggle relies on `document.documentElement.classList.toggle` and `localStorage`, but doesn't handle hydration mismatch natively, which might throw minor console errors during Next.js SSR.
- **Fix:** Make sure the initial render waits until after mounting to determine the styling.

---

## 5. Backend Audit

### Issue: Missing Rate Limiter Infrastructure
- **Severity:** High
- **File:** `backend/app/routes/chat.py`
- **Problem:** Rate limiting is evaluated via a heavy query: `db.query(Message).filter(Message.prompt_timestamp >= one_minute_ago).count()`. 
- **Impact:** With 30 concurrent users querying every few seconds, the database will experience rapid and repeated full or partial index scans. 
- **Fix:** `slowapi` is installed in `requirements.txt` but entirely unused. Implement it. Alternatively, use Redis `INCR` commands with an expiry for instantaneous evaluation of rate limits.

### Issue: Race Conditions on Prompt Counts
- **Severity:** Medium
- **File:** `backend/app/routes/chat.py`
- **Problem:** `user_session.prompt_count += 1` is evaluated statically. If a user bypasses the UI and spams 5 concurrent POST requests, they can bypass the backend limit since the count is read at roughly the same time before changes commit.
- **Fix:** Use an atomic update: `UserSession.prompt_count = UserSession.prompt_count + 1`.

### Issue: Websocket Type Mismatch Bug
- **Severity:** Medium
- **File:** `backend/app/routes/websocket.py` & `websocket_manager.py`
- **Problem:** JWT `payload.get("sub")` parses as a string. However, Python dictionaries treat `1` and `"1"` as different keys. If an event queries `manager.send_to_user(1, msg)`, it will fail because the user is stored natively under `"1"`.
- **Fix:** Cast `user_id = int(payload.get("sub"))` inside the WebSocket authorization block.

---

## 6. Database Audit

### Issue: Completely Missing Indexes on Filtered Columns
- **Severity:** Critical
- **File:** `backend/app/models.py`
- **Problem:** `Message` table has foreign keys for `user_id` and `session_id`, but no composite index for `(user_id, session_id)`. The `prompt_timestamp` field lacks an index.
- **Impact:** Queries validating rate limits, pulling histories, or tracking the timeline will run O(N) full table scans. Under 30 active users producing thousands of rows, this will crater database query speed.
- **Fix:** 
```python
__table_args__ = (
    Index('idx_user_session_time', 'user_id', 'session_id', 'prompt_timestamp'),
)
```

### Issue: N+1 Query in Admin Actions
- **Severity:** High
- **File:** `backend/app/routes/admin.py`
- **Problem:** In `@router.get("/sessions/{session_id}/participants")` and `get_leaderboard()`, the code fetches all `user_sessions`, iterates through them, and runs a secondary lookup: `user = db.query(User).filter(User.id == us.user_id).first()`.
- **Impact:** Fetching the leaderboard for 30 users requires 31 sequential database queries. High latency.
- **Fix:** Implement SQLAlchemy eager loading: `db.query(UserSession).options(joinedload(UserSession.user))`.

---

## 7. Security Audit

- **Hardcoded Secret Key:** `config.py` hardcodes `SECRET_KEY = "change-me...`. An environment variable fallback is severely needed (`os.getenv("SECRET_KEY")`).
- **CORS Misconfiguration:** `allow_origins=["*"]` allows any malicious site to perform authenticated Cross-Site Request Forgery (CSRF) if cookie storage is used, or perform malicious fetching from authenticated browser contexts. Requires strict domain lockdowns.

---

## 8. Performance and Scalability Audit

### Can it support 25-30 concurrent users today? 
**No.** 

If 30 users hit "SEND" simultaneously:
1. 30 requests enter `chat/send`.
2. 30 synchronous DB connections are opened, instantly exhausting the `pool_size` (20) and `max_overflow` (10). The pool reaches capacity `30/30`.
3. An LLM request goes via OpenAI (synchronous client). Due to the `asyncio.Semaphore(5)`, 5 requests are let through. The FastAPI event loop for those requests becomes entirely blocked because the `self.client.chat...` call is synchronous. The DB connection stays open for all 30 users while 25 wait for the semaphore.
4. Because the loop is blocked, other incoming websocket heartbeat pings are ignored, dropping users.
5. Inbound DB queries queue in waiting states until LLM payloads resolve (1-3 seconds later). Latency spikes immensely. 
6. Database runs 30 simultaneous `COUNT()` statements on unindexed strings, pushing CPU usage artificially high.

| Area | Current Risk | Impact at 30 Users | Recommended Fix |
| ---- | ------------ | --------------------- | --------------- |
| Async/Sync Mix | **Critical** | Worker starvation, 502/504 Timeouts | Use `AsyncOpenAI` client. Switch SQLAlchemy to `ext.asyncio`. |
| DB Connection Pool | **High** | Exhaustion (Connection refused) | Close/Release DB connection during the actual LLM generation. |
| Missing Indexes | **High** | CPU bottleneck in MySQL | Add Composite Index on `user_id`, `session_id`, `prompt_timestamp` |
| Active User Query | **Medium** | Severe latency on Admin dashboard | Cache stats in Redis instead of polling history every hit. |

---

## 9. Deployment and DevOps Audit

- **Missing Artifacts:** The repository lacks containerization. There is no `Dockerfile` or `docker-compose.yml`, which prevents easy scale out.
- **Uvicorn Scaling:** To use multiple cores, production assumes running `uvicorn --workers N`. By default, starting `main.py` directly will run 1 worker. 1 worker cannot scale without proper async hygiene.
- **Environment Handling:** `config.py` uses `BaseSettings` reading an `.env`. Production environments need explicit overrides and lack a documented template (`.env.example`).

---

## 10. Dependency Audit

- **SlowAPI (`slowapi==0.1.9`):** Installed but unused. This should replace DB-backed rate limiting.
- **PyMySQL (`pymysql==1.1.1`):** A synchronous driver being used indiscriminately. Switch to `aiomysql`.
- **OpenAI (`openai==1.58.1`):** A fine dependency, but instantiated incorrectly via `OpenAI` instead of `AsyncOpenAI`.

---

## 11. Code Quality Audit

| File | Problem | Severity | Recommended Refactor |
| ---- | ------- | -------- | -------------------- |
| `llm_provider.py` | Sync OpenAI inside `async def` | Critical | Migrate `self.client = OpenAI(...)` to `AsyncOpenAI`. Add `await` to completions call. Adding `Semaphore(5)` is only half the fix. |
| `routes/chat.py` | Holding DB session during LLM | High | Refactor `send_prompt`. Extract configuration parameters, commit session `db.close()`, query LLM, reopen DB dependency for saving message. |
| `routes/admin.py` | N+1 Queries on `user_id` inside explicit python iterators | High | Use SQL `JOIN` or SQLAlchemy `joinedload()` |
| `websocket.py` | `sub` in JWT parsed as String | Medium | Explicit integer cast: `int(payload.get("sub"))` |

---

## 12. Testing Audit

The repository lacks a `tests/` directory.

### Missing Tests & Critical Flows:
- **Load Testing (Missing):** Requires Locust or generic HTTP bombard tool to simulate exactly 25-30 endpoints hitting POST `/chat/send` per minute.
- **Race Condition Testing (Missing):** Send 5 concurrent HTTP requests to `/chat/send` for the same user token to verify if `prompt_count` updates sequentially.
- **Integration Tests (Missing):** Complete session flow: Admin logs in -> Admin creates Session -> User logs in -> User prompts system -> User hits rate limit -> User hits win condition -> Admin leaderboard accurately reflects results.

---

## 13. Prioritized Fix Plan

### Immediate Fixes (Must Do Before Production)
1. **Priority 1: Convert LLM Calls to True Async.** Replace `OpenAI()` with `AsyncOpenAI()` in `llm_provider.py`. *(Effort: Low, Impact: Critical)*
2. **Priority 2: Separate DB I/O from LLM Execution.** Short-circuit DB connections in `send_prompt`. Do not hold the connection object during `await generate_response`. *(Effort: Medium, Impact: Critical)*
3. **Priority 3: Fix Database Indexes.** Update SQLAlchemy models to maintain composite indexes on `Message`. Add index parameters to model columns. *(Effort: Low, Impact: High)*
4. **Priority 4: Un-poll Frontend Notifications.** Delete the `setInterval` in `UserChatPage` to rely purely on the WebSocket. *(Effort: Very Low, Impact: Medium)*

### Important Improvements (Next 1–2 Weeks)
1. **Containerize:** Add a multi-layer `Dockerfile` for Next.js, a local `Dockerfile` for FastAPI, and `docker-compose.yml` merging MySQL, Redis, and apps.
2. **Implement Real Rate Limiting:** Implement `slowapi` or Redis token buckets rather than SQL `COUNT(*)`.
3. **Fix N+1 Iteration Issues:** Implement joined loading.

### Long-Term Improvements
1. **Secure Tokens:** Convert localStorage JWT handling to strict HttpOnly/Secure cookies. (Effort: Medium)
2. **Move to Async SQLAlchemy:** Repave `database.py` with `ext.asyncio` and completely eliminate thread-blocking sync calls anywhere in the architecture.

---

## 14. Final Verdict

At present, **the repository is NOT production-ready**. 
While technically functional for a single local developer, the architectural anti-patterns of injecting slow, synchronous I/O operations directly into an asynchronous event loop mean that **the backend will collapse under load.** 

Attempting to run a live event with 25-30 simultaneous users today will result in extreme latency spikes, connection timeouts, and disconnected WebSockets, due to both thread-starvation and database pool exhaustion. 

The recent addition of an `asyncio.Semaphore(5)` protects against overwhelming the LLM API itself, but does not fix the underlying thread-blocking problems since the HTTP client behind the LLM wrapper remains synchronous.

However, the logic and PRD design are sound. By executing the **Priority 1 and 2 Immediate Fixes** (changing API wrappers to true async models and divorcing the Database session duration from LLM waiting times), the platform can easily scale to handle hundreds of concurrent users without requiring excessive infrastructure changes.
