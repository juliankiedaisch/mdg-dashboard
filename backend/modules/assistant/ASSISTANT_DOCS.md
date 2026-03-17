# AI Assistant Module — Documentation

## Architecture Overview

The AI Assistant module implements a **Retrieval Augmented Generation (RAG)** system that allows users to ask questions against internal documents. Answers always include source references.

### Pipeline Flow

```
User Question
     │
     ▼
Permission Check (assistant.use / assistant.manage)
     │
     ▼
Embedding Service (Ollama → nomic-embed-text)
     │
     ▼
Vector Search  (Qdrant — similarity + permission filtering)
     │
     ▼
Prompt Builder (context + question + chat history)
     │
     ▼
LLM Generation (Ollama → llama3)
     │
     ▼
Answer + Sources → stored in DB → returned to UI
```

---

## Backend Structure

```
backend/modules/assistant/
├── assistant.py              # Module class (Flask Blueprint, init)
├── api/
│   ├── assistant_routes.py   # Chat API (user-facing)
│   └── admin_routes.py       # Admin API (sources, models, pipeline)
├── services/
│   ├── chat_service.py       # Chat session/message CRUD
│   ├── rag_service.py        # RAG orchestration (retrieve → prompt → LLM)
│   ├── source_service.py     # Source config CRUD
│   └── model_service.py      # Ollama model management + config helpers
├── rag/
│   ├── embeddings.py         # Embedding generation via Ollama
│   ├── vector_store.py       # Qdrant vector database interface
│   ├── retriever.py          # Semantic search + reranking
│   └── prompt_builder.py     # Prompt/context assembly
├── sources/
│   ├── base_source.py        # Abstract base class for connectors
│   ├── bookstack_source.py   # BookStack wiki connector
│   └── filesystem_source.py  # Local filesystem connector
├── ingestion/
│   ├── chunker.py            # Text chunking with overlap
│   └── pipeline.py           # Full ingestion pipeline
├── tasks/
│   ├── ingestion_worker.py   # Background worker thread
│   └── scheduler.py          # APScheduler for periodic sync
├── models/
│   ├── chat_session.py       # ChatSession SQLAlchemy model
│   ├── chat_message.py       # ChatMessage SQLAlchemy model
│   ├── source_config.py      # SourceConfig SQLAlchemy model
│   └── assistant_model.py    # AssistantModel + AssistantLog models
├── dashboard/
│   └── metrics_service.py    # Status/metrics for admin dashboard
└── tests/
    └── test_assistant.py     # Test suite
```

## Frontend Structure

```
frontend/src/pages/Assistant/
├── AssistantChatPage.jsx      # Main chat interface
├── AssistantAdminPage.jsx     # Admin management interface
├── components/
│   ├── ChatWindow.jsx         # Message list + input area
│   ├── MessageBubble.jsx      # Individual message display
│   ├── SourceReferences.jsx   # Source citation display
│   └── ChatHistorySidebar.jsx # Session history sidebar
└── services/
    └── assistantApi.js        # API client functions
```

---

## Permissions

| Permission | Capability |
|---|---|
| `assistant.use` | Chat with the AI assistant |
| `assistant.manage` | Configure sources, models, pipeline, view dashboard |

Permissions are registered automatically when the module loads and can be assigned via the Permission Management UI.

---

## API Reference

### Chat API (requires `assistant.use`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/assistant/sessions` | List user's chat sessions |
| `POST` | `/api/assistant/sessions` | Create a new session |
| `GET` | `/api/assistant/sessions/:uuid` | Get session with messages |
| `PUT` | `/api/assistant/sessions/:uuid` | Rename session |
| `DELETE` | `/api/assistant/sessions/:uuid` | Delete session |
| `POST` | `/api/assistant/sessions/:uuid/archive` | Archive session |
| `POST` | `/api/assistant/chat` | Send message (non-streaming) |
| `POST` | `/api/assistant/chat/stream` | Send message (SSE streaming) |
| `POST` | `/api/assistant/messages/:id/feedback` | Rate a message (helpful/incorrect) |

#### POST `/api/assistant/chat`

**Request:**
```json
{
  "message": "How do I reset a password?",
  "session_uuid": "optional-uuid"
}
```

**Response:**
```json
{
  "session_uuid": "abc-123",
  "answer": "To reset a password, go to Settings... [Quelle: Admin Guide]",
  "sources": [
    {
      "title": "Admin Guide",
      "source": "bookstack",
      "url": "https://wiki.example.com/books/1/page/admin-guide",
      "score": 0.95
    }
  ],
  "model": "llama3"
}
```

#### POST `/api/assistant/chat/stream`

Returns Server-Sent Events (SSE):
```
data: {"type": "sources", "data": [...]}
data: {"type": "chunk", "data": "To reset"}
data: {"type": "chunk", "data": " a password..."}
data: {"type": "done", "session_uuid": "abc-123"}
```

### Admin API (requires `assistant.manage`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/assistant/admin/status` | System status dashboard |
| `GET` | `/api/assistant/admin/logs` | View logs |
| `GET/POST` | `/api/assistant/admin/sources` | List / create sources |
| `GET/PUT/DELETE` | `/api/assistant/admin/sources/:id` | Get / update / delete source |
| `POST` | `/api/assistant/admin/sources/:id/test` | Test source connectivity |
| `POST` | `/api/assistant/admin/sources/:id/sync` | Trigger source sync |
| `GET` | `/api/assistant/admin/models` | List installed Ollama models |
| `POST` | `/api/assistant/admin/models/pull` | Pull (download) a model |
| `POST` | `/api/assistant/admin/models/remove` | Remove a model |
| `POST` | `/api/assistant/admin/models/test` | Test a model |
| `GET/POST` | `/api/assistant/admin/config` | Get / set configuration |
| `POST` | `/api/assistant/admin/pipeline/rebuild` | Full index rebuild |
| `POST` | `/api/assistant/admin/pipeline/purge` | Delete all embeddings |
| `GET` | `/api/assistant/admin/pipeline/queue` | View task queue |

---

## Configuration

Environment variables (can be set in `.env` or `docker-compose.yml`):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_API_URL` | `http://localhost:11434` | Ollama API endpoint |
| `VECTOR_DB_URL` | `http://localhost:6333` | Qdrant endpoint |
| `ASSISTANT_MODEL` | `llama3` | Default LLM model |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Default embedding model |

Configuration can also be changed at runtime via the Admin UI (stored in database).

---

## Deployment Guide

### Docker Compose

The `docker-compose.yml` includes Ollama and Qdrant services:

```yaml
ollama:
  image: ollama/ollama:latest
  ports: ["11434:11434"]
  volumes: [ollama-data:/root/.ollama]

qdrant:
  image: qdrant/qdrant:latest
  ports: ["6333:6333"]
  volumes: [qdrant-data:/qdrant/storage]
```

### Initial Setup

1. Start all services:
   ```bash
   docker compose up -d
   ```

2. Pull required models:
   ```bash
   docker exec mdg-ollama ollama pull llama3
   docker exec mdg-ollama ollama pull nomic-embed-text
   ```

3. The assistant module auto-registers when the backend starts.

4. Assign the `assistant.use` and/or `assistant.manage` permissions to users via the Permission Management UI.

5. Configure knowledge sources in the Admin UI (`/assistant/admin`):
   - Add a BookStack instance or local directory
   - Test connectivity
   - Trigger initial sync

### Local Development

For local development without Docker:

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3
ollama pull nomic-embed-text

# Start Qdrant
docker run -p 6333:6333 qdrant/qdrant

# Install Python dependencies
pip install -r backend/requirements.txt

# Run the backend
cd backend && python app.py
```

---

## Source Connectors

### BookStack

Connects to any BookStack instance via its REST API.

**Configuration:**
- `base_url`: BookStack URL (e.g., `https://wiki.example.com`)
- `token_id`: API token ID
- `token_secret`: API token secret

Generate tokens in BookStack: User Profile → API Tokens.

### Filesystem

Monitors a local directory for documents.

**Configuration:**
- `directory`: Absolute path to the document directory
- `recursive`: Whether to scan subdirectories (default: `true`)

**Supported formats:** PDF, DOCX, TXT, Markdown, HTML

---

## Running Tests

```bash
cd backend
pip install pytest
python -m pytest modules/assistant/tests/ -v
```

---

## Adding New Source Connectors

1. Create a new file in `sources/` (e.g., `confluence_source.py`)
2. Implement the `BaseSource` interface:
   ```python
   class ConfluenceSource(BaseSource):
       def fetch_documents(self) -> List[DocumentChunk]: ...
       def sync(self, last_sync=None) -> List[DocumentChunk]: ...
       def test_connection(self) -> Dict[str, Any]: ...
   ```
3. Register it in `ingestion/pipeline.py`:
   ```python
   SOURCE_TYPES = {
       'bookstack': BookStackSource,
       'filesystem': FilesystemSource,
       'confluence': ConfluenceSource,
   }
   ```
4. Add the option to the frontend source form in `AssistantAdminPage.jsx`.
