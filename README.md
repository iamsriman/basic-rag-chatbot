# Archive — document RAG chatbot

This project is a small document-based RAG application:

1. A chat accepts one PDF, TXT, or Markdown document.
2. The backend extracts text, creates overlapping chunks, embeds them, and stores them in ChromaDB with chat/document metadata.
3. Questions are embedded and searched only against the active chat's document.
4. Gemini streams the grounded answer over Server-Sent Events.

## Run locally

Install dependencies with `uv sync`, add `GEMINI_API_KEY` to `.env`, then start the application:

```powershell
uv run uvicorn api:app --app-dir src --reload
```

Open `http://127.0.0.1:8000`.

The frontend is intentionally vanilla HTML, CSS, and JavaScript so the upload, retrieval, and streaming flow remains easy to follow. Chat state is kept in memory for this learning project; ChromaDB persists indexed chunks locally.

## API surface

- `POST /api/chats` creates a chat.
- `POST /api/chats/{chat_id}/document` processes the single document for a chat. Use `replace=true` to explicitly replace it.
- `GET /api/chats/{chat_id}/chunks` returns paginated chunks.
- `POST /api/chats/{chat_id}/messages` returns an SSE stream containing `sources`, `token`, `done`, or `error` events.