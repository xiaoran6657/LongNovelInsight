# Frontend Smoke Test — LongNovelInsight v0.1.0

This document describes how to manually verify the full local product workflow from a fresh start. Each step includes what to check and what to do if it fails.

## Prerequisites

- Backend running: `conda activate LongNovelInsight && cd backend && uvicorn main:app --reload --port 8000`
- Frontend running: `cd frontend && npm run dev`
- Browser open at `http://localhost:5173`

Both must run simultaneously in separate terminals.

---

## 1. Health Check

**Page:** Dashboard (`/`)

- Verify "Backend Status" shows connected with version `0.1.0`
- Verify topic count is displayed
- Stop the backend — the page should show "Connection failed" without white screen
- Restart the backend

## 2. Create Provider

**Page:** Providers (`/providers`)

**Fake provider (safe, no API key needed):**
1. Select "DeepSeek" from the provider preset dropdown
2. Base URL auto-fills to `https://api.deepseek.com`
3. Select a model (e.g., "DeepSeek V4 Flash")
4. Enter a name: `Smoke Test Provider`
5. Enter any API key (e.g., `sk-test12345`)
6. Leave advanced settings collapsed
7. Click Create

**Verify:**
- Provider appears in list with `masked_api_key` showing `sk-...2345`
- Raw API key is NOT visible

**Test connection (real provider only):**
1. With a real API key, click Test
2. Confirmation dialog appears about API consumption
3. Test result shows success or failure with latency

**Fails?** If Test fails with a fake key, that's expected — the error message should display without page crash.

## 3. Create Topic

**Page:** Topics (`/topics`)

1. Click "Create Topic"
2. Enter name: `Smoke Test Topic`
3. Optionally select the provider from step 2
4. Click Create

**Verify:** Topic appears in list with status `created`. Click into it.

## 4. Upload Document

**Page:** Topic Detail (`/topics/:id`)

1. In the Document section, click "Choose File"
2. Select a `.txt` file (UTF-8 encoded, under 200MB)
3. Click Upload

**Verify:**
- Document info appears: filename, encoding, file size, character count, status `uploaded`
- If using a GBK/GB18030 file, the encoding field shows the detected encoding

**Fails?**
- `.txt` only — other file types are rejected with 400
- >200MB files are rejected with 413
- Duplicate uploads are rejected with 409

## 5. Parse Document

**Page:** Topic Detail — Parse section

1. Click "Parse Document"
2. Wait for completion

**Verify:**
- Success message shows chapter count, chunk count, estimated tokens
- Scroll down — Chapters section shows chapter list with indices and titles
- Chunks section shows a preview (text hidden by default; click "Show Text" to reveal)

**Idempotent behavior:**
- Click Parse again — shows "Already parsed" with same stats
- Click "Force Re-parse" to re-run (only needed after document changes)

**Fails?**
- "No document uploaded" — upload a document first
- "Original text file not found" — re-upload
- Old SQLite schema — delete `data/longnovelinsight.sqlite` and restart backend

## 6. Storage

**Page:** Topic Detail — Storage section

**Verify:**
- Total disk usage, database size, and data dir size shown
- Topic-level breakdown includes novel, chunks, and analyses sizes
- Sizes are displayed in human-readable format (KB/MB)

## 7. Run Analysis (real LLM only)

**Warning: This step consumes API credits.**

**Page:** Topic Detail — Analysis section

**Prerequisite:** Provider must have a real API key and be bound to the topic.

**Preview analysis (recommended for initial test):**
1. In the Provider Config panel, verify model and parameters
2. Set `limit_chunks` to 1 (minimum)
3. Click "Run Analysis"
4. A cost warning dialog appears — confirm
5. Wait for all 6 analysis types to complete

**Verify:**
- Progress bar shows completion per type (6/6)
- Summary bar: elapsed time, estimated tokens, per-type status
- Output cards appear below for each type:
  - Overview: summary with scope indicators
  - Characters: card per character with name/role/traits/confidence
  - Relations: A → B cards with direction and status
  - Events: timeline cards with participants and importance
  - Causality: cause → effect chains with strength
  - Themes: theme cards with type and development
- Each card shows evidence quotes and source chunk IDs

**Fails?**
- No provider configured — bind a provider in the Provider Config panel
- No document / not parsed — complete steps 4-5 first
- LLM JSON parse error — try a different model or smaller `limit_chunks`

## 8. Retry / Re-analyze (optional)

- Failed types show "Retry" button
- Successful types show "Re-analyze" button (deepen mode, uses previous output as context)
- Clicking Retry re-runs only that type

## 9. Chat — Create Session & Send Message (real LLM only)

**Warning: This step consumes API credits.**

**Page:** Chat (`/topics/:id/chat`)

1. Click "Chat →" link from Topic Detail page, or navigate to `/topics/:id/chat`

**Create session:**
1. In the left sidebar, type a title (e.g., "Character Discussion") and click New
2. The new session appears in the list (highlighted)

**Send a message:**
1. In the chat input at the bottom, type: `Who are the main characters?`
2. Press Enter or click Send
3. The user message appears in the message area immediately (blue, right-aligned)
4. Wait for the assistant response (warm-yellow, left-aligned)

**Verify:**
- Assistant response includes:
  - Answer text
  - Evidence section with quotes and source references (or "No evidence cited")
  - Uncertainty field if the model isn't confident
  - Timestamp at the bottom

**Fails?**
- No provider configured — use the right panel (expand with ◀ button) Config & Usage tab to check
- 409 error — the topic has no bound provider with a real API key

## 10. Chat — Message Actions

**On any user message, hover** — action buttons appear in the bottom-right corner:

- **Copy (⎘):** Click — copies message text to clipboard, briefly shows ✓
- **Edit (✎):** Click — message becomes an editable textarea. Edit the text, click "Resend". Old message and old LLM response are replaced.
- **Delete (✗):** Click — confirmation dialog. Confirm deletes the message AND the following assistant response.

**On any assistant message, hover:**
- **Copy (⎘):** Same behavior
- **Delete (✗):** Deletes only the assistant message

## 11. Chat — Right Panel

**Expand the right panel:** Click the ◀ button on the right edge.

**Config & Usage tab:**
- Provider Config card shows current settings (Model / Thinking / Max Tokens / Temperature / Base URL)
- Edit a field (e.g., change Thinking to "enabled") — Save / Cancel buttons appear
- Save persists to the topic config; subsequent messages use the new settings
- Chat Usage card shows per-model stats (requests, prompt tokens, completion tokens, total tokens)

**Source tab:**
- Shows the parsed novel text organized by chapter and chunk
- Scroll to verify text is readable and free of excessive blank lines

## 12. Chat — Panel Controls

- **Collapse left sidebar:** Click ◀ next to "Chat Sessions" — sidebar shrinks to a narrow strip. Click ▶ to expand.
- **Collapse right panel:** Click ▶ on the right edge.
- **Resize panels:** Drag the vertical divider bars between panels. Widths are preserved across expand/collapse.

## 13. Delete and Cleanup

1. **Chat:** Delete sessions via the Del button in the sidebar
2. **Analysis Outputs:** From Topic Detail, click "Delete All Outputs" (confirmation required)
3. **Document:** From Topic Detail, delete the document (cascades: removes chapters/chunks/outputs/chat)
4. **Topic:** From Topics list, delete the topic (full cascade)
5. **Provider:** From Providers, delete the provider (blocked if still bound to a topic — unbind first)

**Verify** each delete operation succeeds and the UI updates accordingly.

## 14. Error Scenarios

| Test | Expected |
|------|----------|
| Stop backend, navigate frontend | Health shows connection failed. Other pages show errors without white screen. |
| Upload non-.txt file | 400 rejection with clear message |
| Upload >200MB file | 413 rejection |
| Parse without document | Error message, no crash |
| Run analysis without provider | 409 or warning in UI |
| Send chat without provider | 409 error message |
| Delete provider bound to topic | 409 — provider in use |
| GBK/GB18030 .txt upload | Success with encoding detected |
| Refresh during analysis | Progress recovers from sessionStorage |
| Navigate to unknown URL | NotFoundPage (404) |

## 15. Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| White screen on load | Backend not running or CORS misconfigured | Start backend on port 8000 |
| Health shows "Connection failed" | VITE_API_BASE_URL wrong or backend down | Check `.env.local`, restart backend |
| Parse / analysis 400/500 | Old SQLite schema | Delete `data/longnovelinsight.sqlite`, restart backend |
| Provider test / analysis fails with 401 | Wrong or expired API key | Update provider with valid key |
| GBK file shows garbled text | File is not actually GBK-encoded | Check file properties, try UTF-8 |
| Analysis takes very long | Large `limit_chunks` value | Use 1-3 for testing |
| Chat messages fail to load | Old DB schema (missing token columns) | Restart backend — migration runs on startup |
| CSS changes not visible | Browser cache | Ctrl+F5 hard refresh |
| Right panel source text has excessive blank lines | Old parse data | Force Re-parse to apply whitespace normalization |

## 16. Files You Should NEVER Commit

```
node_modules/
dist/
.env.local
.env.*.local
data/
*.sqlite
*.db
*.txt
agent/
.claude/settings.local.json
Prompts/
MVP/
```

These are already in `.gitignore` — do not use `git add -f` for them.
