import os
from collections import defaultdict
from datetime import datetime
from time import time

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user, hash_password, verify_password
from db import Base, SessionLocal, engine, get_db
from models import Conversation, Message, User

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


class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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


@app.post("/auth/signup", response_model=TokenResponse)
def signup(request: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.query(User).filter(User.email == request.email).first() is not None:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=request.email, hashed_password=hash_password(request.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id))


@app.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == request.email).first()
    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return TokenResponse(access_token=create_access_token(user.id))


@app.post("/conversations", response_model=ConversationOut)
def create_conversation(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Conversation:
    conversation = Conversation(user_id=current_user.id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@app.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .all()
    )


def get_owned_conversation(
    conversation_id: int, db: Session, current_user: User
) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Message]:
    conversation = get_owned_conversation(conversation_id, db, current_user)
    return conversation.messages


def build_history(conversation: Conversation, new_message: str) -> list[dict]:
    history = [{"role": m.role, "content": m.content} for m in conversation.messages]
    history.append({"role": "user", "content": new_message})
    return history


@app.post("/chat/stream")
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
