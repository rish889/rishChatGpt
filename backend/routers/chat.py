import json
from collections import defaultdict
from time import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from db import SessionLocal
from llm import DEFAULT_MODEL, DEFAULT_TEMPERATURE, client
from models import Conversation, Message, User
from rag import retrieve_relevant_chunks
from routers.conversations import TITLE_LENGTH, get_owned_conversation
from tools import TOOL_SCHEMAS, call_tool

router = APIRouter()

RATE_LIMIT_MAX_MESSAGES = 20
RATE_LIMIT_WINDOW_SECONDS = 60 * 60
MAX_TOOL_ITERATIONS = 5

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


def build_history(conversation: Conversation, new_message: str, db: Session) -> list[dict]:
    history = []
    if conversation.system_prompt:
        history.append({"role": "system", "content": conversation.system_prompt})

    if conversation.documents:
        relevant_chunks = retrieve_relevant_chunks(db, conversation.id, new_message)
        if relevant_chunks:
            context = "\n\n---\n\n".join(chunk.content for chunk in relevant_chunks)
            history.append(
                {
                    "role": "system",
                    "content": (
                        "Use the following excerpts from the user's uploaded documents to "
                        "help answer, if relevant. If they aren't relevant, ignore them.\n\n"
                        + context
                    ),
                }
            )

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
        history = build_history(conversation, request.message, db)
    except HTTPException:
        db.close()
        raise

    def token_stream():
        full_reply = []
        try:
            messages = list(history)
            for _ in range(MAX_TOOL_ITERATIONS):
                stream = client.chat.completions.create(
                    model=conversation.model or DEFAULT_MODEL,
                    messages=messages,
                    temperature=(
                        conversation.temperature
                        if conversation.temperature is not None
                        else DEFAULT_TEMPERATURE
                    ),
                    tools=TOOL_SCHEMAS,
                    stream=True,
                )

                content_parts = []
                tool_calls: dict[int, dict] = {}
                finish_reason = None
                for chunk in stream:
                    choice = chunk.choices[0]
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason
                    delta = choice.delta
                    if delta.content:
                        content_parts.append(delta.content)
                        full_reply.append(delta.content)
                        yield delta.content
                    for tc_delta in delta.tool_calls or []:
                        entry = tool_calls.setdefault(
                            tc_delta.index, {"id": "", "name": "", "arguments": ""}
                        )
                        if tc_delta.id:
                            entry["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                entry["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                entry["arguments"] += tc_delta.function.arguments

                if finish_reason != "tool_calls" or not tool_calls:
                    break

                ordered_calls = [tool_calls[i] for i in sorted(tool_calls)]
                messages.append(
                    {
                        "role": "assistant",
                        "content": "".join(content_parts) or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                },
                            }
                            for tc in ordered_calls
                        ],
                    }
                )
                for tc in ordered_calls:
                    try:
                        args = json.loads(tc["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    label = args.get("query") or args.get("expression") or ""
                    yield f"\n[using {tc['name']}: {label}]\n"
                    result = call_tool(tc["name"], args)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result,
                        }
                    )
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
