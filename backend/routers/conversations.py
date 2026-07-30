from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from db import get_db
from llm import ALLOWED_MODELS
from models import Conversation, Message, User

router = APIRouter()

TITLE_LENGTH = 40


class ConversationSettings(BaseModel):
    system_prompt: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    created_at: datetime
    system_prompt: str | None
    model: str | None
    temperature: float | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str


def validate_settings(settings: ConversationSettings) -> None:
    if settings.model is not None and settings.model not in ALLOWED_MODELS:
        raise HTTPException(status_code=400, detail=f"Unsupported model: {settings.model}")


def get_owned_conversation(
    conversation_id: int, db: Session, current_user: User
) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/models", response_model=list[str])
def list_models() -> list[str]:
    return sorted(ALLOWED_MODELS)


@router.post("/conversations", response_model=ConversationOut)
def create_conversation(
    settings: ConversationSettings = ConversationSettings(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Conversation:
    validate_settings(settings)
    conversation = Conversation(
        user_id=current_user.id,
        system_prompt=settings.system_prompt,
        model=settings.model,
        temperature=settings.temperature,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def update_conversation_settings(
    conversation_id: int,
    settings: ConversationSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Conversation:
    validate_settings(settings)
    conversation = get_owned_conversation(conversation_id, db, current_user)
    for field, value in settings.model_dump(exclude_unset=True).items():
        setattr(conversation, field, value)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .all()
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Message]:
    conversation = get_owned_conversation(conversation_id, db, current_user)
    return conversation.messages
