# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A from-scratch "build your own ChatGPT" learning project: a FastAPI backend that wraps the
OpenAI API, a React/Vite chat frontend, and Postgres for persistence. See `BUILD_PLAN.md` for
the full phased roadmap (architecture diagram, tech stack rationale, and a log of what each
phase implemented) — read it before making structural changes, since it explains *why* things
are built the way they are (e.g. why `users` was deferred to Phase 4, why streaming uses plain
chunked text instead of SSE, why rate limiting is in-memory).

Phases 0–8 are done (hello-world script, single-turn chat, streaming chat UI, conversation
history/persistence, auth/multi-user, per-conversation system prompt/model/temperature
settings, per-conversation document RAG, tool use, production hardening). The "deploy" part
of Phase 8 was intentionally skipped — no hosting platform has been chosen yet.

## Commands

Backend (from `backend/`, after `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`):
```
uvicorn main:app --reload          # run API on http://127.0.0.1:8000 (docs at /docs)
```
Requires `backend/.env` (copy from `backend/.env.example`): `OPENAI_API_KEY`, `OPENAI_MODEL`,
`DATABASE_URL`, `JWT_SECRET`. `TAVILY_API_KEY` is optional — without it the `web_search` tool
just tells the model search isn't configured, everything else still works. There is no test
suite and no lint config for the backend.

Frontend (from `frontend/`):
```
npm run dev         # vite dev server on http://localhost:5173
npx tsc --noEmit    # typecheck (do this before/after edits — no test suite exists)
npm run build        # tsc -b && vite build
npm run lint          # oxlint
```

Infra (from `infra/`):
```
docker compose up -d      # build+start postgres, backend (:8000), frontend (:5173)
docker compose down -v    # stop and wipe the volume
```
This now brings up the whole stack, not just Postgres — `backend` and `frontend` services
build from `backend/Dockerfile` / `frontend/Dockerfile` (the latter is a multi-stage
`npm run build` → nginx image). `backend` requires `backend/.env` to exist (loaded via
`env_file`; `DATABASE_URL` is overridden in the compose file to point at the `postgres`
service name rather than `localhost`). The `vector` extension (`CREATE EXTENSION IF NOT
EXISTS vector`) is enabled automatically by `backend/db.py` on startup — the Postgres image
must be `pgvector/pgvector:pg16` (not plain `postgres`) for that to succeed, and `postgres`
has a `pg_isready` healthcheck that `backend` waits on.

There are no automated tests anywhere in this repo. `.github/workflows/ci.yml` runs on
push/PR: a backend job installs `requirements.txt` and runs `python -m compileall` (a
syntax/import sanity check, not real coverage, since there's still no test suite); a
frontend job runs `tsc --noEmit`, `npm run lint`, and `npm run build`. Verify backend
changes locally via `/docs` (Swagger UI) or curl; verify frontend changes with `tsc
--noEmit` plus manually exercising the UI at localhost:5173.

## Architecture

```
Browser (React/Vite)  →  FastAPI backend  →  OpenAI API
                              │
                          Postgres (SQLAlchemy)
```

### Backend (`backend/`)

- `main.py` — FastAPI app setup, CORS (locked to `http://localhost:5173`), mounts routers,
  creates tables on startup via `Base.metadata.create_all`. Calls `configure_logging()` at
  import time and installs an HTTP middleware that logs `METHOD path -> status (Nms)` for
  every request (and `logger.exception(...)` before re-raising on an unhandled error).
- `logging_config.py` — one-line `configure_logging()` (stdlib `logging.basicConfig`),
  called once from `main.py` so log format is consistent everywhere.
- `db.py` — SQLAlchemy engine/session (`SessionLocal`, `get_db` dependency), `DATABASE_URL`
  from env.
- `models.py` — five tables: `User`, `Conversation` (owns `system_prompt`/`model`/
  `temperature` overrides, scoped to a user), `Message` (role + content, ordered by id),
  `Document` and `Chunk` (RAG — see below). `EMBEDDING_DIM` here must match
  `llm.EMBEDDING_MODEL`'s output size.
- `llm.py` — OpenAI client singleton (`timeout=60.0, max_retries=2` — the SDK's own
  exponential-backoff retry for connection errors/timeouts/429/5xx), `DEFAULT_MODEL`,
  `DEFAULT_TEMPERATURE`, and `ALLOWED_MODELS` (the server-side whitelist — any model not in
  this set is rejected with 400 before it reaches the stream); `EMBEDDING_MODEL` and
  `embed_texts()` for RAG; `MODEL_PRICING` (hand-maintained $/1M-token snapshot) and
  `estimate_cost()` for the usage logging in `routers/chat.py`.
- `rag.py` — `extract_text()` (`.txt`/`.md` decoded directly, `.pdf` via `pypdf`),
  `chunk_text()` (character-based, ~1000 chars with 150 overlap — no tokenizer), and
  `retrieve_relevant_chunks()` (pgvector cosine-distance `ORDER BY ... LIMIT` scoped to one
  conversation).
- `tools.py` — the tool-use surface: `TOOL_SCHEMAS` (OpenAI function-calling schemas),
  `web_search` (Tavily API, needs `TAVILY_API_KEY`), `calculate` (arithmetic via a
  whitelisted `ast` walk, never `eval`), and `call_tool(name, arguments)` as the dispatcher
  used by `routers/chat.py`.
- `auth.py` — bcrypt password hashing, JWT issuance/verification (`pyjwt`, 7-day expiry),
  `get_current_user` FastAPI dependency used to gate every conversation/chat/document route.
- `routers/auth.py` — `/auth/signup`, `/auth/login`.
- `routers/conversations.py` — CRUD for conversations/messages/settings, plus
  `get_owned_conversation` (shared helper: 404, not 403, if the conversation belongs to
  someone else — avoids leaking which IDs exist) and `/models` (exposes `ALLOWED_MODELS` so
  the frontend doesn't hardcode a second copy).
- `routers/documents.py` — upload (extract → chunk → embed → store, 5MB cap), list, and
  delete (cascades to chunks) for a conversation's documents. Reuses
  `get_owned_conversation`.
- `routers/chat.py` — `/chat/stream`: per-user in-memory fixed-window rate limiter (20
  messages/hour), builds message history via `build_history` (prepends `system_prompt` if
  set, then — if the conversation has documents — embeds the new message and injects the
  top-4 retrieved chunks as a second system message, then prior messages, then the new one),
  streams OpenAI chat completions as raw text chunks (not SSE-framed). `token_stream` runs a
  bounded loop (`MAX_TOOL_ITERATIONS`), passing `tools=TOOL_SCHEMAS`: it accumulates streamed
  `delta.tool_calls` fragments by index, and on `finish_reason == "tool_calls"` executes each
  call via `tools.call_tool`, appends the assistant tool-call message plus a `tool` message
  per result, and loops back to the model — a `[using <tool>: <args>]` marker is yielded into
  the stream (but excluded from what gets persisted) so the client sees when a tool fires.
  Each API call passes `stream_options={"include_usage": True}` and, once its chunks are
  fully consumed, logs a `usage ...` line (tokens + `llm.estimate_cost` estimate + latency)
  via the stdlib `logging` module. Each iteration's `create()` + chunk consumption is wrapped
  in `try/except openai.APIError`: on failure it logs the exception, yields an
  `[error: ...]` marker (also excluded from persistence), and stops the tool loop — this
  catches failures the SDK's own retries can't cover, like the connection dropping mid-stream
  after content was already sent to the client. Persists both the user message and the full
  assistant reply (tool/error markers excluded) in a `finally` block once the stream ends (so
  partial replies still get saved, and the conversation title is set from the first message).

### Frontend (`frontend/src/`)

- `api.ts` — all backend calls; `apiFetch` wraps `fetch` with the auth header and throws
  `UnauthorizedError` on 401; `streamChat` reads the streamed response via
  `ReadableStream`/`TextDecoder` and invokes a per-chunk callback.
- `auth.ts` — JWT stored in `localStorage`.
- `App.tsx` — top-level state (current conversation, messages, settings, streaming status);
  any `UnauthorizedError` from an API call logs the user out and drops back to `Login`.
  New conversations are created lazily on first send, using whatever settings are currently
  selected.
- `Login.tsx`, `Sidebar.tsx`, `SettingsPanel.tsx`, `Documents.tsx` — auth form, conversation
  list, model/temperature/system-prompt editor, and the attached-files chip list + upload
  control respectively. Uploading a file with no conversation selected yet lazily creates
  one first, mirroring how `sendMessage` in `App.tsx` does it.
- Styling is Tailwind CSS v4 via `@tailwindcss/vite` (no separate Tailwind config file).

### Conventions worth knowing

- Conversation ownership checks always return 404 for a conversation that exists but isn't
  the current user's — never 403 — to avoid confirming an ID's existence to non-owners.
  Reuse `get_owned_conversation` for any new route that touches a conversation.
- Model/temperature validation happens server-side (`validate_settings` /
  `ALLOWED_MODELS`), not just in the frontend dropdown — the frontend list comes from
  `GET /models` precisely so the two can't drift.
- The OpenAI API key is never exposed to the client; all model calls happen in `backend/llm.py`
  and `routers/chat.py`.
