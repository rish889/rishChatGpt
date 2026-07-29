# Build Your Own ChatGPT — End-to-End LLM Platform

Architecture: wrapper on OpenAI's hosted LLM API, not training your own model.
You build the platform around the model — chat UI, backend, auth, history, streaming — and
call out to the model for completions.

## High-level architecture

```
Browser (chat UI)
   │  fetch/streaming (SSE or WebSocket)
   ▼
Backend API (auth, sessions, rate limiting)
   │  server-side SDK call, API key never exposed to client
   ▼
LLM Provider API (OpenAI)
   │
   ▼
Database (users, conversations, messages)
```

## Tech stack (suggested, swap freely)

- Backend: Python (FastAPI)
- Frontend: React + Vite (TypeScript, Tailwind CSS), or Next.js if you want SSR/routing built-in
- DB: Postgres (conversations/messages/users) — SQLite fine for local dev
- Auth: session cookie or JWT; start with a single hardcoded user, add real auth later
- LLM SDK: OpenAI Python SDK (`openai`) — chat completions to start; revisit the Responses API/streaming once Phase 2 lands
- Deployment: Docker Compose locally → Fly.io/Render/Railway for a simple prod deploy

## Phased milestones

### Phase 0 — Hello, model ✅ done
- Single script that sends one prompt to the OpenAI API and prints the response.
- Goal: confirm API key, SDK, and billing work end-to-end.
- Implemented in `backend/hello.py` (see `backend/.env.example` for setup).

### Phase 1 — Minimal backend + single-turn chat ✅ done
- Backend endpoint `POST /chat` that takes a message, calls the LLM, returns the reply.
- No streaming, no persistence, no auth. Plain HTML form or curl is a fine client.

### Phase 2 — Real chat UI + streaming ✅ done
- React (Vite + TypeScript + Tailwind) chat UI: message list, input box, send button, loading state.
- Backend gained `POST /chat/stream`, which streams the OpenAI response as raw text chunks
  (not full SSE framing — a plain chunked `text/plain` response, consumed via `fetch` +
  `ReadableStream` on the frontend). Simpler than SSE while still streaming incrementally.
- This is the first point it "feels like ChatGPT."
- Implemented in `frontend/` (see `frontend/src/App.tsx`) and `backend/main.py`.

### Phase 3 — Conversation history & persistence
- DB schema: `users`, `conversations`, `messages`.
- Backend maintains conversation context (send prior messages back to the model).
- UI: sidebar with past conversations, ability to start a new chat / resume one.

### Phase 4 — Auth & multi-user
- Real login (email+password or OAuth).
- Conversations scoped per user; rate limiting per user to control API cost.

### Phase 5 — System prompts, model/parameter controls
- Let users (or you, as admin) configure system prompt, temperature, model choice.
- Add a model picker if supporting multiple providers/models.

### Phase 6 — Tool use / RAG (optional, advanced)
- File upload → embed → retrieve → inject into context (basic RAG).
- Or: give the model tools (web search, code execution) via the provider's tool-use API.

### Phase 7 — Production hardening
- Streaming error handling/retries, request timeouts, cost/usage logging.
- Dockerize, add CI, deploy, add basic observability (logs/metrics).

## Suggested repo layout once you start coding

```
/backend      API server, LLM integration, DB models
/frontend     React chat UI
/infra        Dockerfile, docker-compose.yml, deploy config
BUILD_PLAN.md this file
```

## Next step

Phases 0–2 are done. Next: Phase 3 — conversation history & persistence (DB schema for
users/conversations/messages, backend sends prior messages back to the model, UI sidebar
with past conversations).
