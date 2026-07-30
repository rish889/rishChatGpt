from collections import defaultdict
from time import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_current_user
from db import SessionLocal
from llm import DEFAULT_MODEL, DEFAULT_TEMPERATURE, client
from models import Conversation, Message, User
from routers.conversations import TITLE_LENGTH, get_owned_conversation

router = APIRouter()

RATE_LIMIT_MAX_MESSAGES = 20
RATE_LIMIT_WINDOW_SECONDS = 60 * 60

_rate_limit_log: dict[int, list[float]] = defaultdict(list)


def check_rate_limit(user_id: int) -> None:
    now = time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    timestamps = [t for t in _rate_limit_log[user_id] if t > window_start]
    if len(timestamps) >= RATE_LIMIT_MAX_MESSAGES:
        raise HTTPException(status_code=429, detail="Rate limit exceeded, try again later")
    timestamps.append(now)
    _rate_limit_log[user_id] = timestamps


class ChatRequest(BaseModel):
    conversation_id: int
    message: str


def build_history(conversation: Conversation, new_message: str) -> list[dict]:
    history = []
    if conversation.system_prompt:
        history.append({"role": "system", "content": conversation.system_prompt})
    history.extend({"role": m.role, "content": m.content} for m in conversation.messages)
    history.append({"role": "user", "content": new_message})
    return history


@router.post("/chat/stream")
def chat_stream(
    request: ChatRequest, current_user: User = Depends(get_current_user)
) -> StreamingResponse:
    check_rate_limit(current_user.id)

    db = SessionLocal()
    try:
        conversation = get_owned_conversation(request.conversation_id, db, current_user)
        history = build_history(conversation, request.message)
    except HTTPException:
        db.close()
        raise

    def token_stream():
        full_reply = []
        try:
            stream = client.chat.completions.create(
                model=conversation.model or DEFAULT_MODEL,
                messages=history,
                temperature=(
                    conversation.temperature
                    if conversation.temperature is not None
                    else DEFAULT_TEMPERATURE
                ),
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_reply.append(delta)
                    yield delta
        finally:
            db.add(
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content=request.message,
                )
            )
            if full_reply:
                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content="".join(full_reply),
                    )
                )
            if conversation.title is None:
                conversation.title = request.message[:TITLE_LENGTH]
            db.commit()
            db.close()

    return StreamingResponse(token_stream(), media_type="text/plain")
