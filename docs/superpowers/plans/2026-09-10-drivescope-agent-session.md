# DriveScope Agent Session and Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed backend sequence with a real DeepSeek-V4-Flash tool-calling loop that owns the first `classify_car` call, persists multi-turn sessions, and exposes a truthful chat/trace/archive workflow.

**Architecture:** Uploads are stored locally behind a controlled `image_ref`; DeepSeek receives only text plus that reference. A bounded orchestrator executes only validated tools requested by DeepSeek, persists messages/tool runs/context in SQLite, and force-stops unknown or low-confidence classification. React renders the same session response, actual tool arguments/results/timings, archive history, and the existing mouse-following depth scene.

**Tech Stack:** FastAPI, Pydantic, SQLite, requests, PyTorch/Pillow, React 19, TypeScript, Vite, Vitest.

**Spec:** `E:/浏览器下载/视觉智能体综合实训：学生任务书.pdf`

## Global Constraints

- Model name is exactly `deepseek-v4-flash`.
- `DEEPSEEK_API_KEY` is read only by the backend; never persist or return its value.
- DeepSeek receives no image bytes or data URL; only a validated `image_ref`.
- The first main-flow model response must contain a `classify_car` tool call.
- Unknown or low-confidence classification stops downstream vehicle tools in program code.
- No teacher test set means no fabricated `predictions.csv`.

### Task 1: Red tests for the agent protocol and session persistence

**Files:**
- Create: `tests/test_agent_runtime.py`
- Create: `tests/test_archive_history_api.py`
- Modify: `tests/test_agent_chain.py`

- [ ] Assert the first model request is forced to `classify_car`, includes only the controlled image reference, and never includes image bytes.
- [ ] Assert tool calls are dispatched from model responses rather than a backend sequence, and each trace row includes validated arguments, result summary, status, and duration.
- [ ] Assert unknown classification returns after `classify_car` and does not execute later tools.
- [ ] Assert a second request on the same session can use the stored classification without re-uploading.
- [ ] Assert archive save and text search persist across a fresh store instance.
- [ ] Run focused tests and confirm expected import/behavior failures before production implementation.

### Task 2: Implement storage, schemas, DeepSeek loop, and routes

**Files:**
- Create: `backend/session_store.py`
- Create: `backend/agent_runtime.py`
- Modify: `backend/deepseek_client.py`
- Modify: `backend/services.py`
- Modify: `backend/schemas.py`
- Modify: `backend/routes/agent.py`
- Modify: `backend/routes/catalog.py`
- Modify: `backend/main.py`

- [ ] Add SQLite tables for sessions, image references, messages, tool runs, and vehicle archives with idempotent migration.
- [ ] Define JSON schemas for `classify_car`, `query_car_info`, `search_vehicle_views`, `generate_design_language`, `build_design_board`, `save_vehicle_archive`, and `search_archive_history`.
- [ ] Implement the bounded response loop with a maximum turn count, function-call argument validation, tool failure recording, and no secret logging.
- [ ] Persist the user message, assistant tool calls, tool results, final answer, context, and archive result under one `session_id`.
- [ ] Add upload-safe image refs and text-only `/api/agent` continuation, `/api/session/{id}`, and `/api/archives` search endpoints.
- [ ] Run focused tests, then the complete backend suite.

### Task 3: Redesign the React workflow around chat and real traces

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/ToolRail.tsx`
- Modify: `frontend/src/styles.css`
- Create/modify: `frontend/src/App.test.tsx`

- [ ] Add tests for upload-plus-message, text-only follow-up, unknown stop, rendered real trace summaries, archive search, and responsive chat controls.
- [ ] Implement persistent session state, upload preview, conversation transcript, input composer, and saved archive/history panel.
- [ ] Render backend-provided tool names, arguments, results, status, and duration; remove phase-derived fake completion counts.
- [ ] Keep and refine the mouse-following 3D depth effect, with reduced-motion and mobile-safe behavior.
- [ ] Run Vitest and the production build.

### Task 4: End-to-end verification and truthful documentation

**Files:**
- Modify: `README.md`
- Modify: `build_manual.py`
- Update: `output/DriveScope汽车视觉智能体实训讲解手册.docx`

- [ ] Run backend tests, frontend tests, and production build.
- [ ] Start FastAPI and Vite, verify desktop and mobile rendered pages, and exercise upload → classify → archive → text follow-up → history search.
- [ ] Verify no API key appears in source, logs, frontend assets, responses, or documentation.
- [ ] Verify task-book claims against actual code and mark teacher-test `predictions.csv` as pending.
- [ ] Update README/manual with the actual tool protocol, storage, model metrics, limitations, and commands.
