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
- DB: Postgres (conversations/messages/users), run locally via Docker Compose (`infra/docker-compose.yml`)
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

### Phase 3 — Conversation history & persistence ✅ done
- DB schema: `conversations`, `messages` (Postgres via SQLAlchemy, run locally with
  Docker Compose — see `infra/docker-compose.yml`). `users` deferred to Phase 4 — no
  point in a users table nothing references until real auth exists.
- Backend maintains conversation context: `/chat` and `/chat/stream` load prior messages
  for a `conversation_id` from the DB, send them back to the model, then persist the new
  turn (title auto-set from the first message).
- UI: sidebar (`frontend/src/Sidebar.tsx`) listing past conversations, "+ New chat", click
  to resume. New conversations are created lazily on first send.
- Implemented in `infra/docker-compose.yml`, `backend/db.py`, `backend/models.py`,
  `backend/main.py`, and `frontend/src/{App.tsx,Sidebar.tsx,api.ts}`.

### Phase 4 — Auth & multi-user ✅ done
- Real login: email+password signup/login, `bcrypt` password hashing, JWT (`pyjwt`,
  7-day expiry) issued on login/signup and sent as `Authorization: Bearer <token>`.
- `users` table added (deferred from Phase 3); `conversations.user_id` scopes every
  conversation to its owner. All conversation/chat endpoints require
  `Depends(get_current_user)` and 404 (not 403) on conversations owned by someone else,
  to avoid leaking which IDs exist.
- Rate limiting: simple in-memory per-user fixed-window limiter (20 messages/hour) on
  `/chat/stream`, since that's the endpoint that actually spends OpenAI credits. In-memory
  is fine for a single-process learning app; revisit (Redis) if this ever runs multi-process.
- UI: `frontend/src/Login.tsx` (login/signup form), token stored in `localStorage`
  (`frontend/src/auth.ts`), attached to every API call in `frontend/src/api.ts`. A 401
  anywhere logs the user out and drops them back to the login screen.
- Implemented in `backend/auth.py`, `backend/models.py`, `backend/main.py`, and
  `frontend/src/{App.tsx,Login.tsx,Sidebar.tsx,api.ts,auth.ts}`.

### Phase 5 — System prompts, model/parameter controls ✅ done
- `conversations` gained `system_prompt`, `model`, `temperature` columns. Settings are
  per-conversation: set them before the first message (applied when the conversation is
  lazily created) or mid-conversation via `PATCH /conversations/{id}` (applies to the next
  turn).
- `build_history` prepends a `system` message when `system_prompt` is set; `chat_stream`
  uses `conversation.model or DEFAULT_MODEL` and `conversation.temperature` (falls back to
  `1.0`, OpenAI's default). Model choice is validated server-side against `ALLOWED_MODELS`
  (400 on anything else) so a bad value fails fast instead of erroring inside the stream.
  `GET /models` exposes the allowed list so the UI doesn't hardcode a second copy.
- UI: "Settings" button in the header opens `frontend/src/SettingsPanel.tsx` — model
  dropdown, temperature slider, system prompt textarea. Selecting a past conversation loads
  its saved settings.
- Implemented in `backend/models.py`, `backend/main.py`, and
  `frontend/src/{App.tsx,SettingsPanel.tsx,api.ts}`.

### Phase 6 — RAG ✅ done
- `documents`/`chunks` tables (Postgres via `pgvector`, image switched to
  `pgvector/pgvector:pg16` in `infra/docker-compose.yml`); documents are scoped to a
  conversation, not a user, so retrieval never crosses conversations.
- `POST /conversations/{id}/documents` extracts text (`.txt`/`.md` decoded directly, `.pdf`
  via `pypdf`), splits it into ~1000-char overlapping chunks, embeds each chunk with
  `text-embedding-3-small`, and stores chunk + embedding. `GET`/`DELETE` round out listing
  and removal (cascades to its chunks).
- `chat_stream`'s `build_history` embeds the new user message and pulls the top-4 chunks for
  that conversation by cosine distance (pgvector `<=>`), skipping the embedding call entirely
  when the conversation has no documents. Retrieved chunks are injected as a separate system
  message ("use if relevant, ignore if not") ahead of prior turns.
- UI: a chip list + "+ Attach file" control (`frontend/src/Documents.tsx`) sits above the
  message input; uploading before any message exists lazily creates the conversation first,
  same as sending a message does.
- Implemented in `backend/{db.py,models.py,llm.py,rag.py,routers/documents.py,
  routers/chat.py,main.py}`, `infra/docker-compose.yml`, and
  `frontend/src/{api.ts,Documents.tsx,App.tsx}`.

### Phase 7 — Tool use ✅ done
- `backend/tools.py` defines the tool-use surface: `TOOL_SCHEMAS` (OpenAI function-calling
  schemas), a `web_search` tool backed by the Tavily API (`TAVILY_API_KEY`, keyless-free
  results if unset — it just tells the model search isn't configured), a `calculate` tool
  that evaluates arithmetic via a whitelisted `ast` walk (no `eval`, so it can't run
  arbitrary code), and `call_tool(name, arguments)` as the dispatcher.
- `chat_stream`'s `token_stream` now runs a bounded loop (`MAX_TOOL_ITERATIONS = 5`): it
  calls the model with `tools=TOOL_SCHEMAS`, accumulates streamed `delta.tool_calls`
  fragments by index (id/name/arguments all arrive piecemeal), and on `finish_reason ==
  "tool_calls"` executes each call, appends the assistant tool-call message plus a `tool`
  role message per result, and loops back to the model with the extended history. It stops
  looping (and starts persisting) once a turn finishes with plain content instead of a tool
  call.
- Tool invocations are surfaced to the client as plain `[using <tool>: <args>]` lines
  interleaved in the raw text stream (consistent with the existing non-SSE streaming
  approach) but are *not* included in `full_reply`, so they never get persisted to the
  `messages` table — only the model's real reply is saved.
- Implemented in `backend/{tools.py,routers/chat.py,requirements.txt,.env.example}`. No
  frontend changes needed — the existing raw-text stream renderer just displays the tool
  markers inline.

### Phase 8 — Production hardening
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

Phases 0–7 are done.
