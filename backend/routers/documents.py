from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import get_current_user
from db import get_db
from llm import embed_texts
from models import Chunk, Document, User
from rag import chunk_text, extract_text
from routers.conversations import get_owned_conversation

router = APIRouter()

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    created_at: datetime


@router.post("/conversations/{conversation_id}/documents", response_model=DocumentOut)
def upload_document(
    conversation_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    conversation = get_owned_conversation(conversation_id, db, current_user)

    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    try:
        text = extract_text(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No extractable text found in file")

    embeddings = embed_texts(chunks)

    document = Document(conversation_id=conversation.id, filename=file.filename or "untitled")
    db.add(document)
    db.flush()

    for chunk_content, embedding in zip(chunks, embeddings):
        db.add(
            Chunk(
                document_id=document.id,
                conversation_id=conversation.id,
                content=chunk_content,
                embedding=embedding,
            )
        )
    db.commit()
    db.refresh(document)
    return document


@router.get("/conversations/{conversation_id}/documents", response_model=list[DocumentOut])
def list_documents(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Document]:
    conversation = get_owned_conversation(conversation_id, db, current_user)
    return conversation.documents


@router.delete("/conversations/{conversation_id}/documents/{document_id}", status_code=204)
def delete_document(
    conversation_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    conversation = get_owned_conversation(conversation_id, db, current_user)
    document = db.get(Document, document_id)
    if document is None or document.conversation_id != conversation.id:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(document)
    db.commit()
