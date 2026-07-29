import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from db import Base, SessionLocal, engine, get_db
from models import Conversation, Message

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

Base.metadata.create_all(bind=engine)

TITLE_LENGTH = 40


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    created_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str


class ChatRequest(BaseModel):
    conversation_id: int
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.post("/conversations", response_model=ConversationOut)
def create_conversation(db: Session = Depends(get_db)) -> Conversation:
    conversation = Conversation()
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@app.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db)) -> list[Conversation]:
    return db.query(Conversation).order_by(Conversation.created_at.desc()).all()


@app.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(conversation_id: int, db: Session = Depends(get_db)) -> list[Message]:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation.messages


def build_history(conversation: Conversation, new_message: str) -> list[dict]:
    history = [{"role": m.role, "content": m.content} for m in conversation.messages]
    history.append({"role": "user", "content": new_message})
    return history


@app.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    db = SessionLocal()
    conversation = db.get(Conversation, request.conversation_id)
    if conversation is None:
        db.close()
        raise HTTPException(status_code=404, detail="Conversation not found")

    history = build_history(conversation, request.message)

    def token_stream():
        full_reply = []
        try:
            stream = client.chat.completions.create(
                model=model, messages=history, stream=True
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
