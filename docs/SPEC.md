# LongNovelInsight v0.1.0 — Product Specification

## Overview

LongNovelInsight is a local-first web application that uses LLMs to analyze long-form novels (.txt) and produce structured literary insights. All data stays on the user's machine. The user brings their own LLM API key.

## User Flow

1. Open browser at `http://localhost:5173` (frontend dev server).
2. Configure an LLM provider — enter API base URL and API key (DeepSeek or any OpenAI-compatible endpoint). This can be done before or after creating a Topic.
3. Create a new Topic (e.g., "Romance of the Three Kingdoms Analysis"). No provider is required at creation time.
4. Bind a provider to the Topic (if not already done), then upload one `.txt` novel file to the Topic.
5. The system parses the novel: splits into chapters, then into chunks, computes token/word/disk statistics.
6. Trigger analysis — the system calls the bound LLM provider to generate six analysis types:
   - Work overview
   - Character list
   - Character relationships
   - Key events
   - Event causal chain
   - Theme / philosophy analysis
7. Browse analysis results in the frontend. Each result includes evidence quotes and references back to source chunks.
8. Ask free-form questions in the Topic's chat. Answers are grounded in existing analysis and relevant source chunks.
9. View storage usage, task/job progress, and analysis status in the UI.
10. Delete any Topic (including its novel, analysis, and chat history) at any time.

## Feature Scope (v0.1.0)

1. **LLM Provider Configuration** — Users can add, edit, and delete LLM provider configurations (API base URL, API key, model name). Default: DeepSeek (`https://api.deepseek.com`).
2. **Topic CRUD** — Create, list, update, and delete Topics. A Topic groups one novel and all its analysis/chat data. Provider binding is optional at creation; required before running analysis or chat.
3. **Novel Upload (.txt only)** — Upload one `.txt` file per Topic. Accepts UTF-8 and GBK encodings. Auto-detects encoding.
4. **Novel Parsing** — Split the novel into chapters (by regex patterns: "第X章", "Chapter X", etc.) and chunks (fixed token window with overlap). Compute token count, word count, and disk size for each chunk.
5. **LLM Analysis Pipeline** — Run six analysis types against the configured LLM. All outputs MUST include `source_chunk_ids`, `evidence_quotes`, and `confidence` fields. See [LLM_PIPELINE.md](LLM_PIPELINE.md).
6. **Topic Chat (Q&A)** — Users can ask questions within a Topic. The system retrieves relevant analysis outputs and source chunks, then sends them as context to the LLM for grounded answers.
7. **Local Data Storage** — All data stored in SQLite database and `data/` directory. No network calls except to the configured LLM API.
8. **Delete Operations** — Users can delete a Topic (cascading: novel file, analysis results, chat history). Users can also delete individual chat sessions or analysis outputs.
9. **Storage & Progress UI** — Frontend displays: total disk usage, per-Topic usage, token/word/chunk counts, analysis job status (pending/running/done/failed).
10. **Job System** — Long-running operations (novel parsing, analysis pipeline) run as background jobs with status tracking. The frontend polls job status.
11. **Health Check** — `GET /api/health` returns backend status and basic stats.

## Non-Goals (v0.1.0)

These are explicitly excluded from v0.1.0:

1. No login / authentication / authorization system.
2. No multi-user support.
3. No cloud sync or remote storage.
4. No multi-novel Topics — one Topic = one `.txt` novel.
5. No `.epub` or PDF parsing — `.txt` only.
6. No Docker or containerization.
7. No LangChain or similar LLM orchestration frameworks.
8. No vector databases (Chroma, Pinecone, Milvus, etc.).
9. No Redis / Celery / PostgreSQL / message queues.
10. No plugin system or extension API.
11. No graph/chart visualization (character network graphs, etc.) — text and tables only.
12. No complex abstractions or premature generalization — keep it simple.

## Acceptance Criteria (v0.1.0)

### AC-1: LLM Provider Setup
- User can create a provider config with base URL, API key, and model name.
- Connection test succeeds against a real DeepSeek or OpenAI-compatible endpoint.
- Invalid configs show clear error messages.

### AC-2: Topic & Novel Upload
- User can create a Topic with a name and optional description.
- User can upload a `.txt` file (up to 200 MB, configurable in `backend/config.py`) to a Topic.
- Non-`.txt` files are rejected with a clear error.
- GBK-encoded files are auto-detected and converted to UTF-8.

### AC-3: Novel Parsing
- Novel is correctly split into chapters (handles Chinese and English chapter patterns).
- Each chapter is split into chunks of approximately equal token count.
- Token count, word count, and byte size are computed per chunk.
- Parsing progress is reported as a job.

### AC-4: Analysis Pipeline
- All six analysis types complete successfully against the configured LLM.
- Every analysis output includes `source_chunk_ids`, `evidence_quotes`, and `confidence`.
- Analysis progress is reported as a job with per-type status.
- If one analysis type fails, others continue (independent jobs).

### AC-5: Chat Q&A
- User can create a chat session within a Topic.
- User can send questions and receive grounded answers.
- Answers reference specific analysis outputs and source chunks.
- Chat history is preserved across page reloads.

### AC-6: Data Management
- Deleting a Topic removes its novel file, analysis results, and chat history from both SQLite and disk.
- Storage usage stats update after delete operations.
- No orphaned data remains after deletion.

### AC-7: Storage & Status UI
- Frontend shows total disk usage and per-Topic breakdown.
- Job progress is visible (pending → running → done/failed).
- Analysis results are displayed in structured tables with evidence quotes.

### AC-8: All Data Local
- The only outbound network traffic is to the user-configured LLM API.
- No analytics, telemetry, or phoning home.
- `data/` and `*.sqlite` are in `.gitignore`.

## Constraints

- Backend: Python 3.11+, FastAPI, SQLModel, SQLite
- Frontend: React 18+, TypeScript strict mode, Vite
- LLM: OpenAI-compatible chat completions API (DeepSeek v3 by default)
- OS: Windows, macOS, Linux
- Browser: Chrome, Firefox, Edge (latest 2 versions)
