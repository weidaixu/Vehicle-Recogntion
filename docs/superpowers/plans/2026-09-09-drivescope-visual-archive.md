# DriveScope Visual Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a React and FastAPI vehicle design studio that identifies a car, asks DeepSeek for its design language, retrieves licensed multi-view imagery, and exports a visual research board inside an immersive racing interface.

**Architecture:** A Vite React client calls a FastAPI service over `/api`. The backend wraps the existing classifier and dataset, calls DeepSeek only from the server, enriches local imagery with licensed Wikimedia Commons results, and renders downloadable boards. A Three.js background is isolated from business state and degrades to a static rotated photograph.

**Tech Stack:** React 19, TypeScript, Vite, Framer Motion, Three.js, React Three Fiber, FastAPI, Pydantic, PyTorch, Pillow, SQLite, pytest, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-09-drivescope-frontend-design.md`

## Global Constraints

- Rotate the supplied photograph clockwise by 90 degrees and preserve the original file unchanged.
- Use `#141713`, `#4C4538`, `#9C9A90`, `#D5D7D2`, `#D92D32`, and `#F3EEDD` as the complete theme palette.
- DeepSeek credentials stay server-side and never appear in frontend assets, logs, or API status responses.
- Network images require author, license, source page, and modification metadata; local dataset images remain the offline fallback.
- Respect `prefers-reduced-motion` and provide a non-WebGL static fallback.
- Keep the existing Streamlit app as a fallback; the React app becomes the primary showcase.
- Current lightweight CNN remains the functional baseline; model optimization is outside this migration.

---

### Task 1: Backend API foundation and status contract

**Files:**
- Create: `backend/main.py`
- Create: `backend/schemas.py`
- Create: `backend/services.py`
- Create: `tests/test_status_api.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `GET /api/status -> StatusResponse` with `model_ready`, `class_count`, `macro_f1`, `deepseek_configured`, and `webgl_assets_ready`.
- Produces: shared `classifier_service`, `catalog_service`, and `trace_store` dependencies.

- [ ] Write a FastAPI test asserting `/api/status` returns HTTP 200, `class_count == 51`, a numeric `macro_f1`, and a boolean `deepseek_configured` without exposing an API key.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest tests/test_status_api.py -v` and confirm it fails because `backend.main` does not exist.
- [ ] Add FastAPI, uvicorn, python-multipart, httpx, pytest, and reportlab to `requirements.txt`; implement typed Pydantic responses and lifespan-loaded classifier/catalog services.
- [ ] Configure CORS for `http://localhost:5173` only in development and add a `/api/health` lightweight endpoint that does not load the model.
- [ ] Run the status test and require PASS; run `python -m py_compile backend/main.py backend/schemas.py backend/services.py`.

### Task 2: Image classification and catalog endpoints

**Files:**
- Create: `backend/routes/classification.py`
- Create: `backend/routes/catalog.py`
- Create: `tests/test_classification_api.py`
- Create: `tests/test_catalog_api.py`
- Modify: `backend/main.py`

**Interfaces:**
- Produces: `POST /api/classify` multipart fields `image` and `threshold`, returning `label`, `raw_label`, `confidence`, `top_k`, `rejected`, and `trace_id`.
- Produces: `GET /api/cars?q=&limit=` and `GET /api/cars/{class_id}`.

- [ ] Write tests using `prepared/val/0006/0006_0004.jpg`, covering successful inference, invalid image bytes, threshold bounds, search by ID/name, and a 404 class ID.
- [ ] Run both test files and confirm endpoint-not-found failures.
- [ ] Implement MIME/size validation, PIL decoding, calls to `VehicleClassifier.classify_car`, class-name enrichment from `class_info.json`, and sanitized error responses.
- [ ] Add one trace entry per classification with tool name, timestamps, arguments excluding image bytes, status, and summarized result.
- [ ] Run the tests and require PASS; confirm the earlier UploadedFile/file-like regression test still passes.

### Task 3: DeepSeek design-language tool

**Files:**
- Create: `backend/routes/design_language.py`
- Create: `backend/deepseek_client.py`
- Create: `tests/test_design_language_api.py`
- Modify: `backend/schemas.py`
- Modify: `backend/main.py`

**Interfaces:**
- Produces: `POST /api/design-language` with `session_id`, `class_id`, and optional `user_focus`.
- Returns: `summary`, `proportions`, `lighting_signature`, `surface_language`, `aerodynamics`, `brand_cues`, `limitations`, and `trace_id`.

- [ ] Write tests with an injected fake DeepSeek transport, asserting the exact structured response, missing-key HTTP 503 behavior, invalid model output HTTP 502 behavior, and no credential leakage.
- [ ] Run the test and confirm failure because the route is absent.
- [ ] Implement a timeout-bound DeepSeek client using `deepseek-v4-flash`, JSON Schema tool output, server-side `DEEPSEEK_API_KEY`, and defensive JSON validation.
- [ ] Ground the prompt only in `name_from_new`, `type_info`, classifier confidence, and explicit uncertainty; forbid invented specifications such as horsepower or dimensions.
- [ ] Record `generate_design_language` in the trace store and run the tests to PASS.

### Task 4: Multi-view visual archive service

**Files:**
- Create: `backend/routes/vehicle_views.py`
- Create: `backend/wikimedia.py`
- Create: `tests/test_vehicle_views_api.py`
- Modify: `backend/main.py`

**Interfaces:**
- Produces: `GET /api/vehicle-views/{class_id}?network=true&limit=12`.
- Each item contains `url`, `thumbnail_url`, `source_kind`, `view_hint`, `author`, `license_name`, `license_url`, `source_page`, and `modified`.

- [ ] Write tests for deterministic local-image retrieval, mocked Wikimedia search and imageinfo metadata, rejected entries without a license, network timeout fallback, and unknown class IDs.
- [ ] Run the tests and confirm route-not-found failures.
- [ ] Implement local retrieval from `train/{class_id}` and `val/{class_id}` without copying original datasets; expose images through a safe allow-listed file route.
- [ ] Implement Wikimedia Commons search with timeouts, result limits, User-Agent, metadata normalization, and exclusion of entries missing source or license fields.
- [ ] Merge and de-duplicate local/network items, label uncertain angles as `未标注视角`, and record `search_vehicle_views` in the trace store.
- [ ] Run tests to PASS with network fully mocked.

### Task 5: Design-board export and agent orchestration

**Files:**
- Create: `backend/routes/design_board.py`
- Create: `backend/routes/agent.py`
- Create: `backend/board_renderer.py`
- Create: `tests/test_agent_chain.py`
- Create: `tests/test_design_board.py`
- Modify: `backend/main.py`

**Interfaces:**
- Produces: `POST /api/design-board` returning a downloadable PNG and attribution manifest ID.
- Produces: `POST /api/agent` returning `session_id`, `answer`, `classification`, `design_language`, `views`, `board_url`, and ordered `trace`.

- [ ] Write a board test asserting image dimensions, visible title text, at least three image cells, and a companion JSON attribution manifest.
- [ ] Write an agent-chain test with fake DeepSeek and Wikimedia transports; assert ordered tools `classify_car`, `query_car_info`, `generate_design_language`, `search_vehicle_views`, `build_design_board`.
- [ ] Run tests and confirm failures because renderer and routes do not exist.
- [ ] Implement a Pillow board renderer with theme colors, Chinese font fallback, model result, design-language sections, image cells, and a numbered attribution footer.
- [ ] Implement a session store that retains the latest class ID and allows text-only follow-ups without re-uploading an image.
- [ ] Implement orchestration that stops after rejected classification, continues through all tools on a confident result, and reports each failure truthfully.
- [ ] Run both tests to PASS and inspect one generated board image at original resolution.

### Task 6: React application foundation and rotated hero asset

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/global.css`
- Create: `frontend/public/assets/hero-car.jpg`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/types/api.ts`

**Interfaces:**
- Consumes: all `/api` contracts from Tasks 1-5.
- Produces: typed `api` client methods and global visual tokens.

- [ ] Write Vitest tests for status loading, API error normalization, and the presence of the three primary workspace modes.
- [ ] Run `npm test` and confirm initial failures.
- [ ] Scaffold Vite React TypeScript, proxy `/api` to port 8000, and define the exact six-color token palette, spacing, typography, glass, and focus tokens.
- [ ] Rotate the supplied source photograph clockwise 90 degrees with Pillow, resize it to a web-appropriate maximum of 2560 pixels, and save a high-quality optimized JPEG while preserving the source.
- [ ] Build the app shell with hero copy, system metrics, navigation for `识别`, `设计语言`, `视觉档案`, `设计板`, and `工具轨迹`, plus loading/error boundaries.
- [ ] Run tests and `npm run build`; require PASS and no TypeScript errors.

### Task 7: Three.js racing background and motion system

**Files:**
- Create: `frontend/src/scene/RacingScene.tsx`
- Create: `frontend/src/scene/DepthLayer.tsx`
- Create: `frontend/src/hooks/useReducedMotion.ts`
- Create: `frontend/src/components/RacingHud.tsx`
- Create: `frontend/src/styles/motion.css`
- Test: `frontend/src/scene/RacingScene.test.tsx`

**Interfaces:**
- Consumes: `phase: 'idle' | 'scanning' | 'success' | 'error'` and normalized pointer/scroll input.
- Produces: WebGL background with static `<picture>` fallback and HUD state synchronized to inference.

- [ ] Write component tests asserting static fallback, reduced-motion behavior, canvas isolation, and phase-dependent accessible labels.
- [ ] Run tests and confirm failures.
- [ ] Implement three perspective planes for mountain, ground, and vehicle-focused layers using the rotated photo with different UV offsets and depth response.
- [ ] Implement clamped pointer/touch parallax, one-time radial-blur entrance, tail-light glow, scanning pulse, and a frame-rate guard that disables WebGL after sustained low performance.
- [ ] Implement HUD tick animation and ensure all continuous animation stops or simplifies under `prefers-reduced-motion`.
- [ ] Run tests and `npm run build`; inspect desktop and mobile screenshots for crop and text contrast.

### Task 8: High-fidelity workflow UI

**Files:**
- Create: `frontend/src/features/classify/ClassifyPanel.tsx`
- Create: `frontend/src/features/design/DesignLanguagePanel.tsx`
- Create: `frontend/src/features/archive/VisualArchive.tsx`
- Create: `frontend/src/features/board/DesignBoardPanel.tsx`
- Create: `frontend/src/features/trace/ToolTrace.tsx`
- Create: `frontend/src/components/MagneticButton.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: complete identify-to-board user flow and downloadable result.
- Consumes: typed API client and `RacingScene` phase state.

- [ ] Write tests for file selection, classify request, rejected result, successful design-language request, archive fallback label, board download link, and ordered trace rendering.
- [ ] Run tests and confirm failures.
- [ ] Implement drag/drop image preview, scan overlay, confidence arc, Top-3 display, and explicit unknown guidance.
- [ ] Implement structured design-language cards, source-aware image gallery, attribution drawer, and downloadable design-board preview.
- [ ] Implement restrained magnetic hover, light sweep, spring panel transitions, keyboard focus, and touch-safe alternatives.
- [ ] Run tests and `npm run build`; require PASS.

### Task 9: End-to-end startup, verification, and documentation

**Files:**
- Create: `scripts/start_drivescope.ps1`
- Create: `frontend/e2e/drivescope.spec.ts`
- Modify: `README.md`
- Modify: `build_manual.py`
- Update: `output/车型识别智能体实训讲解手册.docx`

**Interfaces:**
- Produces: one-command local startup and final student-facing documentation.

- [ ] Implement a PowerShell launcher that starts FastAPI on 8000 and Vite on 5173, checks both health endpoints, prints URLs, and stops both child processes on exit.
- [ ] Write Playwright tests for page identity, rotated background, WebGL/static fallback, image upload, classification, design language, archive, trace, download, network failure, and mobile layout.
- [ ] Run backend pytest, frontend Vitest, Vite production build, and Playwright; require all suites to pass.
- [ ] Start the real app, upload a dataset image, execute the full tool chain, inspect browser console warnings/errors, and capture desktop plus mobile screenshots.
- [ ] Update README and the DOCX manual with architecture, setup, API Key boundary, three core functions, tool sequence, screenshots, limitations, and exact startup commands.
- [ ] Render the DOCX to PNG when the bundled renderer is available; otherwise perform structural checks and clearly record the missing LibreOffice visual-QA limitation.

## Completion Gate

- [ ] All backend and frontend tests pass.
- [ ] Production frontend build succeeds.
- [ ] Real browser flow completes without uncaught console errors.
- [ ] The supplied photograph is correctly rotated and rendered as an immersive depth scene.
- [ ] Tool trace proves at least three actual tool calls.
- [ ] Final manual and source code contain no API keys or fabricated model results.
