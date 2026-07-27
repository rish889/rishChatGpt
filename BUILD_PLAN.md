# Build Your Own ChatGPT — End-to-End LLM Platform

Architecture: wrapper on a hosted LLM API (Anthropic/OpenAI), not training your own model.
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
LLM Provider API (Claude / GPT)
   │
   ▼
Database (users, conversations, messages)
```

## Tech stack (suggested, swap freely)

- Backend: Node.js (Express/Fastify) or Python (FastAPI)
- Frontend: React + Vite, or Next.js if you want SSR/routing built-in
- DB: Postgres (conversations/messages/users) — SQLite fine for local dev
- Auth: session cookie or JWT; start with a single hardcoded user, add real auth later
- LLM SDK: Anthropic Python/TS SDK (or OpenAI SDK) — see `claude-api` skill for model IDs/pricing/streaming details
- Deployment: Docker Compose locally → Fly.io/Render/Railway for a simple prod deploy

## Phased milestones

### Phase 0 — Hello, model
- Single script that sends one prompt to the LLM API and prints the response.
- Goal: confirm API key, SDK, and billing work end-to-end.

### Phase 1 — Minimal backend + single-turn chat
- Backend endpoint `POST /chat` that takes a message, calls the LLM, returns the reply.
- No streaming, no persistence, no auth. Plain HTML form or curl is a fine client.

### Phase 2 — Real chat UI + streaming
- React chat UI: message list, input box, send button, loading state.
- Switch backend to stream tokens (SSE) so replies appear incrementally.
- This is the first point it "feels like ChatGPT."

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

Start at Phase 0 in a new `/backend` directory: pick Node or Python, install the LLM SDK,
and get one script printing a real model response before touching any UI or DB code.
