import json
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chunker import create_chunks
from embedding import create_embeddings
from llm import generate_answer_stream
from retriever import retrieve
from vector_store import collection, add_documents


ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)


@dataclass
class Chat:
    chat_id: str
    title: str
    document: dict[str, Any] | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)


chats: dict[str, Chat] = {}
app = FastAPI(title="Document RAG Chatbot")
app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")


class Question(BaseModel):
    question: str


def get_chat(chat_id: str) -> Chat:
    chat = chats.get(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return chat


def serialize_chat(chat: Chat) -> dict[str, Any]:
    document = None
    if chat.document:
        document = {
            key: value
            for key, value in chat.document.items()
            if key != "stored_path"
        }
    return {
        "chat_id": chat.chat_id,
        "title": chat.title,
        "document": document,
        "messages": chat.messages,
    }


def extract_document(path: Path, filename: str) -> tuple[list[str], list[dict[str, Any]]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        pages: list[str] = []
        with fitz.open(path) as document:
            pages = [page.get_text() for page in document]
        chunks: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for page_number, page_text in enumerate(pages, start=1):
            page_chunks = create_chunks(page_text)
            chunks.extend(page_chunks)
            metadatas.extend({"page": page_number} for _ in page_chunks)
        return chunks, metadatas

    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8")
        chunks = create_chunks(text)
        return chunks, [{} for _ in chunks]

    raise HTTPException(
        status_code=415,
        detail="Upload a PDF, TXT, or Markdown document.",
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.post("/api/chats")
def create_chat() -> dict[str, Any]:
    chat_id = str(uuid.uuid4())
    chat = Chat(chat_id=chat_id, title="New conversation")
    chats[chat_id] = chat
    return serialize_chat(chat)


@app.get("/api/chats")
def list_chats() -> list[dict[str, Any]]:
    return [
        {
            "chat_id": chat.chat_id,
            "title": chat.title,
            "document": serialize_chat(chat)["document"],
        }
        for chat in chats.values()
    ]


@app.get("/api/chats/{chat_id}")
def read_chat(chat_id: str) -> dict[str, Any]:
    return serialize_chat(get_chat(chat_id))


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str) -> dict[str, bool]:
    chat = get_chat(chat_id)
    collection.delete(where={"chat_id": chat_id})
    if chat.document:
        Path(chat.document["stored_path"]).unlink(missing_ok=True)
    del chats[chat_id]
    return {"deleted": True}


@app.post("/api/chats/{chat_id}/document")
async def upload_document(
    chat_id: str,
    file: UploadFile = File(...),
    replace: bool = Form(False),
) -> dict[str, Any]:
    chat = get_chat(chat_id)
    if chat.document and not replace:
        raise HTTPException(
            status_code=409,
            detail="This chat already has a document. Replace it or create a new chat.",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="Choose a document to upload.")

    document_id = str(uuid.uuid4())
    stored_path = UPLOADS / f"{document_id}{Path(file.filename).suffix.lower()}"
    with stored_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    try:
        chunks, metadatas = extract_document(stored_path, file.filename)
        if not chunks:
            raise HTTPException(status_code=400, detail="The document has no readable text.")
        embeddings = create_embeddings(chunks)
        if chat.document:
            collection.delete(where={"chat_id": chat_id})
            Path(chat.document["stored_path"]).unlink(missing_ok=True)

        add_documents(
            chunks,
            embeddings,
            chat_id=chat_id,
            document_id=document_id,
            metadatas=metadatas,
        )
        chat.document = {
            "document_id": document_id,
            "name": file.filename,
            "content_type": file.content_type or "application/octet-stream",
            "size": stored_path.stat().st_size,
            "chunk_count": len(chunks),
            "status": "ready",
            "stored_path": str(stored_path),
        }
        chat.title = Path(file.filename).stem[:48] or "Document conversation"
        return serialize_chat(chat)
    except HTTPException:
        stored_path.unlink(missing_ok=True)
        raise
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Document processing failed. Please try again.")


@app.get("/api/chats/{chat_id}/chunks")
def list_chunks(chat_id: str, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    chat = get_chat(chat_id)
    if not chat.document:
        raise HTTPException(status_code=404, detail="Upload a document first.")
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="Invalid chunk pagination.")

    result = collection.get(
        where={"chat_id": chat_id},
        include=["documents", "metadatas"],
    )
    rows = sorted(
        zip(result["ids"], result["documents"], result["metadatas"]),
        key=lambda row: int(row[0].rsplit("_", 1)[-1]),
    )
    start = (page - 1) * page_size
    items = [
        {
            "id": chunk_id,
            "number": start + index + 1,
            "text": text,
            "metadata": metadata or {},
            "source": chat.document["name"],
        }
        for index, (chunk_id, text, metadata) in enumerate(rows[start : start + page_size])
    ]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": len(rows),
        "pages": (len(rows) + page_size - 1) // page_size,
    }


def event(name: str, payload: Any) -> str:
    return f"event: {name}\ndata: {json.dumps(payload)}\n\n"


@app.post("/api/chats/{chat_id}/messages")
def stream_message(chat_id: str, body: Question) -> StreamingResponse:
    chat = get_chat(chat_id)
    question = body.question.strip()
    if not chat.document:
        raise HTTPException(status_code=400, detail="Upload a document before asking questions.")
    if not question:
        raise HTTPException(status_code=400, detail="Enter a question.")

    chat.messages.append({"id": str(uuid.uuid4()), "role": "user", "content": question})
    assistant_id = str(uuid.uuid4())

    def generate():
        answer_parts: list[str] = []
        try:
            results = retrieve(question, top_k=3, chat_id=chat_id)
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            sources = [
                {
                    "number": index + 1,
                    "text": text,
                    "metadata": metadata or {},
                    "source": chat.document["name"],
                }
                for index, (text, metadata) in enumerate(zip(documents, metadatas))
            ]
            yield event("sources", sources)
            context = "\n\n".join(documents)
            for response in generate_answer_stream(question, context):
                token = getattr(response, "text", None)
                if token:
                    answer_parts.append(token)
                    yield event("token", token)
            answer = "".join(answer_parts)
            chat.messages.append(
                {
                    "id": assistant_id,
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                }
            )
            yield event("done", {"message_id": assistant_id})
        except Exception:
            yield event("error", {"message": "The response was interrupted. Try again."})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
