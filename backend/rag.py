import io

from pypdf import PdfReader
from sqlalchemy.orm import Session

from llm import embed_texts
from models import Chunk

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
TOP_K = 4


def extract_text(filename: str, content: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("txt", "md"):
        return content.decode("utf-8", errors="ignore")
    if ext == "pdf":
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise ValueError(f"Unsupported file type: .{ext or '?'} (use .txt, .md, or .pdf)")


def chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def retrieve_relevant_chunks(db: Session, conversation_id: int, query: str) -> list[Chunk]:
    query_embedding = embed_texts([query])[0]
    return (
        db.query(Chunk)
        .filter(Chunk.conversation_id == conversation_id)
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(TOP_K)
        .all()
    )
