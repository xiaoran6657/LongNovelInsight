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

---

## 17. v0.2 Analysis Run — Creation & Polling

**Prerequisites:** A Topic with document uploaded, parsed, and provider bound with complete config.

### 17.1 Chunks Meta + Range Selection

1. Navigate to the topic detail page
2. Verify "Chunks Meta" card shows: chunk count, chapter count, total chars, estimated tokens
3. Verify "Range Selection" section appears below with radio buttons: "By chunk index" / "By chapter index"
4. Set start=0, end=5 in chunk mode — verify "Selected: 6 chunks"
5. Set invalid range (start=5, end=0) — verify error message
6. Switch to "By chapter index" — verify inputs switch context

### 17.2 Analysis Mode Selection

1. Verify 4 mode options: Preview, Range, Full, Incremental
2. Select "Preview" — verify limit_chunks input appears
3. Select "Range" — range selector becomes active for run scope
4. Select "Full" — verify orange warning text appears
5. Select "Incremental" — if no previous run, verify it is disabled with explanation
6. Verify "Cost Projection" card updates when mode/range changes

### 17.3 Create v2 Run

1. Select "Preview" mode with limit_chunks=3
2. Click "Run v2 Analysis"
3. Verify API consumption warning is visible
4. Verify active run card appears with status badge (pending → running → succeeded)
5. Verify progress bar appears during running state
6. Verify polling indicator shows "Polling..."
7. Wait for completion — verify progress bar disappears and "Complete" text appears

### 17.4 Full Mode Confirmation

1. Select "Full" mode
2. Click "Run v2 Analysis" — verify red confirmation box with chunk count appears
3. Click "Cancel" — verify confirmation is dismissed
4. Click "Run v2 Analysis" again — verify confirmation reappears
5. Click "Yes, run full analysis" — verify run begins

### 17.5 Cancel Run

1. Create a run with many chunks so it takes time
2. Verify "Cancel" button is visible with red background
3. Click "Cancel" — verify status changes to "cancelled"
4. Verify cancel button disappears after cancellation

### 17.6 Stage Progress

1. After run completes, verify three stage bars: Extraction, Merge, Final Outputs
2. Verify each bar shows succeeded/failed/total counts
3. If extraction failures exist, verify failed items listed (max 20) with "+N more" overflow
4. Verify warnings section in a collapsible `<details>` element

---

## 18. v0.2 Run History & Actions

### 18.1 Run History List

1. Verify "Run History" section appears below the active run panel
2. If no runs exist, verify EmptyState with "No runs yet" message
3. Create several runs — verify they appear in reverse chronological order
4. Verify each run shows: mode, StatusBadge, date, extraction/merge counts, tokens, model
5. If more than 10 runs, verify only first 10 are shown with "Show all N runs" button
6. Click "Show all" — verify all runs appear
7. Click "Show less" — verify list collapses back to 10

### 18.2 Select Run from History

1. Click a run row in history — verify it highlights (blue border)
2. Verify the outputs panel updates to show that run's outputs
3. Click the same row again — verify deselection

### 18.3 Retry Failed / Resume

1. For a run with `partial_success` or `failed` status:
   - Verify "Retry Failed" and "Resume" buttons appear in the history row
   - Verify same buttons appear in the active run display when selected
2. Click "Retry Failed" — verify run status changes to pending/running
3. Click "Resume" — verify run resumes polling

### 18.4 Inline Retry in Active Run

1. Select a run with `partial_success` or `failed` status
2. Verify the active run card shows "Retry Failed" and "Resume" buttons above error message
3. Click "Retry Failed" — verify mutation starts and queries invalidate

---

## 19. v0.2 Refresh Resilience

### 19.1 Active Run Persistence

1. Create a v2 run and note the run ID
2. While the run is still pending/running, refresh the page (F5)
3. Verify the active run card reappears and polling resumes automatically
4. Verify the run ID is stored in `sessionStorage` under key `activeAnalysisRun_<topicId>`
5. Wait for the run to reach terminal state
6. Verify the `sessionStorage` key is removed
7. Refresh again — verify no run is auto-selected

### 19.2 Backend Unavailable Recovery

1. While viewing a topic detail page with run history, stop the backend
2. Verify all three panels show ErrorBlock with retry button:
   - Run History: "Failed to load run history"
   - Outputs: "Failed to load analysis outputs"
   - Chunks Meta: "Failed to load chunk metadata"
3. Verify ErrorBlock shows HTTP status badge (e.g., `[0]` for network error)
4. Restart the backend
5. Click "Retry" on each panel — verify data reloads successfully
6. For the active run, verify polling resumes after backend restart

### 19.3 404 Run Recovery

1. Select a run from history
2. Delete the run externally (or simulate 404)
3. Verify the active run display clears without crashing
4. Verify sessionStorage key is removed

---

## 20. v0.2 Outputs & StatusBadge

### 20.1 Outputs Panel

1. After a run completes with outputs, verify outputs appear in the outputs panel
2. Verify output type filter dropdown works
3. If some output types are missing, verify orange "Missing types" card
4. If a run is still active, verify "Analysis is still running" note
5. Verify "Delete All" button with confirmation dialog works
6. Verify output cards show type name, truncated run ID, date, and content

### 20.2 EmptyState and StatusBadge

1. When no runs exist, verify "No runs yet" EmptyState with description
2. When no outputs exist, verify "No analysis outputs yet" EmptyState
3. Verify all status displays use the StatusBadge component with proper coloring:
   - succeeded: green, failed: red, partial_success: orange, running: blue

---

## 21. v0.2 Error Detail Expansion

1. Trigger an API error (e.g., stop backend)
2. Verify ErrorBlock shows an expandable "Show details" section
3. Click "Show details" — verify error detail text appears in a scrollable pre block
4. Verify long detail text is truncated at 500 characters with "..."
5. Verify HTTP status badge appears (e.g., `[404]`, `[500]`) when applicable

---

## 22. Keyboard Accessibility

1. Tab through the page — verify run history rows receive focus with visible outline
2. Press Enter or Space on a focused run row — verify it selects/deselects
3. Verify all buttons have keyboard-operable focus styles
4. Verify disabled buttons are skipped in tab order or clearly indicated
5. Verify aria-labels exist on: Retry Failed, Resume, Cancel, Create Run, Delete All buttons
