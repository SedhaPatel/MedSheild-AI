# MedShield-AI Clinical PACS Workstation (Option 1) — Skill-Orchestrated Implementation Plan & Prompt Blueprint

> **For agentic workers:** REQUIRED SUB-SKILL: Execute each phase sequentially through the mapped workspace skills in `d:\ISC-Project\.agents\skills\`, tracking steps with `- [ ]` checkboxes and honoring `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`.

**Goal:** Redesign the MedShield-AI frontend from scratch as a true diagnostic radiology PACS workstation (`frontend/`) using **React 19 + TypeScript + Vite + Cornerstone3D + Tailwind CSS + shadcn/ui (Radix) + Zustand**, connected to FastAPI, orchestrated end-to-end via the repository's skill pipeline without generic AI card-grid bloat.

**Architecture:** Decoupled SPA (`frontend/`) served on Vite (`:5173`) in dev (proxying `/api` to FastAPI `:8000`) and compiled as static assets for production. **Cornerstone3D** (`@cornerstonejs/core`, `@cornerstonejs/tools`, `@cornerstonejs/dicom-image-loader`) renders raw decrypted 12–16-bit DICOM Part 10 instances streamed from FastAPI in WebGL with continuous Window Width / Window Center (WW/WC) drag adjustment, polarity invert, zoom/pan, and a synchronized Grad-CAM heatmap canvas overlay layer. State lives in Zustand stores (`studyQueueStore`, `viewportStore`, `securityAuditStore`).

**Tech Stack:**
- **Frontend Runtime & Bundler:** React 19, TypeScript 5.x, Vite 6.x, `@originjs/vite-plugin-commonjs` (for `dicom-parser`)
- **Medical Imaging Engine:** `@cornerstonejs/core`, `@cornerstonejs/tools`, `@cornerstonejs/dicom-image-loader`, `dicom-parser`
- **UI Primitives & Styling:** Tailwind CSS + `shadcn/ui` (Radix UI primitives) + `lucide-react` + `IBM Plex Sans` / `IBM Plex Mono`
- **State & Networking:** `zustand` + native `fetch` (`safeApiClient`) + Vite dev proxy
- **Backend Host (Existing):** Python 3.14 + FastAPI (`medshield/api/app.py`, `routes/studies.py`, `routes/inference.py`, `routes/dashboard.py`)

**Specs & Existing Contracts:**
- Core system spec: `SPEC.md`
- Baseline reading-room design tokens: `.interface-design/system.md`
- Existing tests: `tests/test_api_endpoints.py` (29 backend tests must stay 100% green)

---

## Global Constraints

- **No Streamlit, No Generic Card Slop:** Do not use generic rounded SaaS metric cards, neon cyan glow shadows, raw `alert()`/`confirm()` dialogs, or placeholder mock predictions.
- **Keep FastAPI Backend Functional:** Existing routes in `medshield/api/routes/studies.py`, `inference.py`, and `dashboard.py` must continue passing `python -m pytest tests/ -v`.
- **Cornerstone3D Vite Build Safety:** `vite.config.ts` MUST configure `viteCommonjs()`, `worker: { format: 'es' }`, `optimizeDeps.exclude: ['@cornerstonejs/dicom-image-loader']`, and `optimizeDeps.include: ['dicom-parser']` so Web Workers and WASM codecs bundle cleanly.
- **Clinical Light-Box Ergonomics:** Dark reading-room surfaces (`#0C0E13` base, `#13161D` panels, `1px` `rgba(255,255,255,0.07)` borders, WCAG AA >= 4.5:1 text contrast), dominant diagnostic canvas (>= 60% width), toggleable non-blocking Grad-CAM overlay, and radiologist keyboard hotkeys (`W`/`L` Window-Level mode, `I` invert, `1/2/3` layer modes, `+/-/0` zoom/reset).
- **Zero Unhandled Non-JSON Errors:** API client wrapper must check `res.ok` and read `await res.text()` safely before `JSON.parse()` so HTTP 500 plain-text responses never raise `SyntaxError: Unexpected token`.
- **Token Compliance:** UI primitives must consume semantic CSS variables (generated/validated via `design-system` scripts) — never hardcoded random hex inside components.
- **Do Not Push Remotely:** Commit locally per phase only; never execute `git push` unless explicitly authorized later.

---

## Review Focus (Top 5 Failure Modes to Verify)

1. **Cornerstone3D Web Worker / WASM Boot Failure:** Loading a `.dcm` instance in Vite without excluding `@cornerstonejs/dicom-image-loader` from pre-bundling breaks `new URL(..., import.meta.url)` worker instantiation with runtime `SyntaxError` or blank canvas. Verify live DICOM pixel rendering in headless Chromium.
2. **MONOCHROME1 Photometric Inversion & Missing DICOM File Meta:** Chest radiographs with `PhotometricInterpretation == "MONOCHROME1"` or uploaded `.png` scans wrapped into DICOM fail unless Cornerstone imageId loaders or backend Part 10 normalization supply `file_meta` + 128-byte preamble. Test both `.dcm` and `.png` ingestion.
3. **Crypto-Shredding Leakage Across Studies:** Triggering DPDP Section 12 erasure on Study A must fail decryption for Study A (`403`/`404`/`CRYPTO_SHREDDED`) while leaving Study B completely readable. Verify via automated API + UI click test.
4. **Grad-CAM Alignment Drift Under Zoom/Pan:** Panning or zooming the DICOM viewport must keep the Grad-CAM saliency overlay aligned pixel-for-pixel with lung anatomy, and toggling/adjusting opacity (`0%–100%`) must never black out or distort the base radiograph.
5. **Dual-Server CORS / Proxy Mismatch in Live Browser:** Running Vite on `:5173` and FastAPI on `:8000` causes CORS or binary `arrayBuffer()` streaming failures on WADO/DICOM byte downloads unless `vite.config.ts` proxies `/api` and FastAPI `CORSMiddleware` exposes binary headers. Verify full network log shows zero failed fetches.

---

## Master Skill-Orchestrated Prompt (Copy-Paste Ready)

Use this prompt cleanly in a fresh agent session (with **Turbo / auto-approve** enabled) to execute the entire Option 1 redesign strictly following the repository skill sequence:

```text
Redesign the MedShield-AI frontend from scratch using Option 1 (React 19 + TypeScript + Vite + Cornerstone3D + Tailwind CSS + shadcn/ui + Zustand) in `frontend/`, connected to our FastAPI backend (`medshield/api/`). Keep existing Python backend tests passing, work in Turbo/autonomous mode without stopping for trivial permissions, and DO NOT run `git push`.

Execute these exact workspace skills in sequence, reading each skill's `SKILL.md` first and producing its real output artifact before moving to the next phase:

PHASE 1 — DISCOVER & ALIGN REQUIREMENTS
1. Invoke `/deep-research` (Autonomous mode) and `/brainstorming`:
   - Inspect `SPEC.md`, `medshield/api/routes/{studies,inference,dashboard}.py`, `medshield/ml/inference_engine.py`, and `test_samples/`.
   - Benchmark production radiology AI & PACS interfaces (OHIF Viewer, Cornerstone3D, Aidoc, RadiAnt): triage worklists sorted by clinical urgency, continuous Window Width/Window Center (WW/WC), side-by-side raw vs. scrubbed comparison, non-intrusive Grad-CAM saliency overlays, and keyboard-first workflows.
   - Lock down the functional specification in `docs/superpowers/specs/YYYY-MM-DD-react-pacs-frontend-design.md`.

PHASE 2 — DEFINE DATA CONTRACTS
2. Invoke `/frontend-to-backend-requirements`:
   - Inspect `medshield/api/routes/studies.py`, `inference.py`, and `dashboard.py`.
   - Document exact data needs in `.claude/docs/ai/clinical-workstation/backend-requirements.md` covering:
     (a) Study ingestion & worklist queue listing (`GET /api/v1/studies` or triage worklist endpoint with anonymized StudyUID, modality, urgency badge, timestamp);
     (b) Decrypted sanitized DICOM Part 10 binary stream endpoint (`GET /api/v1/studies/{study_uid}/dicom`) so Cornerstone3D `wadouri:` / `wadors:` loads genuine 12/16-bit pixels client-side;
     (c) Inference scores + epistemic uncertainty + raw/resized Grad-CAM overlay endpoints;
     (d) Side-by-side HIPAA Safe Harbor metadata diff + burned-in pixel redaction flag;
     (e) Envelope cryptographic metrics (Shannon entropy, SHA-256 digest, 64B binary wire header hex, scoped study KEK ID) & per-study DPDP Section 12 Crypto-Shredding.
   - Implement any missing FastAPI endpoints needed in `medshield/api/routes/` with unit tests in `tests/test_api_endpoints.py` and verify `python -m pytest tests/ -v` passes 100%.

PHASE 3 — VISUAL TOKENS & SYSTEM RULES
3. Invoke `/ui-ux-pro-max`:
   - Run `python .agents/skills/ui-ux-pro-max/scripts/search.py "medical radiology PACS security workstation dark" --design-system --variance 5 --motion 4 --density 9 -p "MedShield-AI" -f markdown`
   - Also run stack queries: `--stack react` and `--stack shadcn`.
4. Invoke `/interface-design`:
   - Inspect/update `.interface-design/system.md` with the React + Cornerstone3D layout hierarchy (Triage Worklist 260px left rail | Cornerstone3D Reading Viewport dominant center + collapsible Safe Harbor audit drawer/panel | Diagnostic Triage + AES-256-GCM Envelope + Two-step DPDP Erasure 320px right rail), IBM Plex typography, WCAG AA contrast >= 4.5:1, zero decorative neon glow, zero modal `alert()`/`confirm()`.
5. Invoke `/design-system`:
   - Define 3-layer CSS tokens (`primitive -> semantic -> component`) matching `.interface-design/system.md` inside `frontend/tokens.json` and run `node .agents/skills/design-system/scripts/generate-tokens.cjs` -> `frontend/src/styles/tokens.css`, then wire into Tailwind CSS v4/v3 theme variables.

PHASE 4 — IMPLEMENTATION PLAN & BUILD
6. Invoke `/writing-plans` to refine granular task diffs, then execute with `/subagent-driven-development` (or `/executing-plans`) alongside `/ui-styling`:
   - Scaffold `frontend/` with Vite + React + TypeScript + Tailwind + shadcn/ui (Radix Dialog/AlertDialog for two-step crypto-shredding, Tabs, Slider, Table, Tooltip, Badge, Toast/Sonner).
   - Configure `frontend/vite.config.ts` specifically for Cornerstone3D (`@originjs/vite-plugin-commonjs`, `worker: { format: 'es' }`, `optimizeDeps.exclude: ['@cornerstonejs/dicom-image-loader']`, `optimizeDeps.include: ['dicom-parser']`, and `/api` proxy to `http://127.0.0.1:8000`).
   - Build `CornerstoneViewport.tsx` supporting real DICOM loading (`wadouri:` blob/endpoint), mouse-drag Window/Level (WW/WC), zoom/pan, grayscale Invert (`I`), and synchronized Grad-CAM heatmap overlay blending (`0%–100%` opacity + selectable pathology target without pixel distortion).
   - Validate token usage using `node .agents/skills/design-system/scripts/validate-tokens.cjs --dir frontend/src/` and ensure `npm run build` (`tsc -b && vite build`) exits cleanly with 0 TypeScript/bundle errors.

PHASE 5 — LIVE VERIFICATION & VISUAL AUDIT
7. Invoke `/webapp-testing`:
   - Use `.agents/skills/webapp-testing/scripts/with_server.py` to launch FastAPI (`:8000`) and Vite (`:5173`) simultaneously (`BypassSandbox: true` on Windows if browser testing requires external socket bind).
   - Run an end-to-end Playwright script inspecting:
     (a) Initial empty/worklist state at desktop (`1440x900`) and mobile (`390x844`);
     (b) Clicking 1-click reference case & uploading `test_samples/patient_01_pneumonia.dcm` and `.png`;
     (c) Verifying non-empty WebGL/Canvas rendering, toggling Original / De-identified / Grad-CAM layers, dragging opacity, clicking a pathology row to re-target Grad-CAM, inspecting Safe Harbor table + Shannon entropy (>= 7.99), and executing inline two-step Crypto-Shredding while proving Study B remains ingestible afterward;
     (d) Capturing screenshots and inspecting them with `read_file` to verify zero overlap, legible contrast, and authentic reading-room craft.
8. Invoke `/verification-before-completion`:
   - Run fresh `python -m pytest tests/ -v`, `npm --prefix frontend run build`, and Playwright browser suite; fix any visual or console/network errors until all pass cleanly with zero skipped assertions. Stop without pushing.
```

---

## Phased Technical Implementation Tasks

Follow Tasks 1–8 below when executing the plan (`docs/superpowers/plans/2026-11-12-react-cornerstone3d-frontend-redesign.md`).

### Phase 1 & 2: Discovery, Contracts & FastAPI Cornerstone3D Endpoints

#### Task 1: Research, Spec & Backend Requirements Contract
**Skills:** `/deep-research`, `/brainstorming`, `/frontend-to-backend-requirements`
**Files:**
- Create: `docs/superpowers/specs/2026-11-12-react-pacs-frontend-design.md`
- Create: `.claude/docs/ai/clinical-workstation/backend-requirements.md`

- [ ] **Step 1:** Read `SPEC.md`, `medshield/api/routes/studies.py`, `medshield/api/routes/inference.py`, and `medshield/api/routes/dashboard.py` completely.
- [ ] **Step 2:** Write `docs/superpowers/specs/2026-11-12-react-pacs-frontend-design.md` capturing clinical workflow requirements (Worklist triage priority queue, Cornerstone3D WW/WC viewport + dual-layer Grad-CAM, DICOM Safe Harbor side-by-side table, FIPS 140-3 crypto verification, DPDP Section 12 two-step shred).
- [ ] **Step 3:** Follow `frontend-to-backend-requirements/SKILL.md` to write `.claude/docs/ai/clinical-workstation/backend-requirements.md` defining UI data needs, error states, and upload/download flows.

---

#### Task 2: Add Decrypted DICOM Stream & Worklist Endpoints for Cornerstone3D
**Files:**
- Modify: `medshield/api/routes/dashboard.py` (or `medshield/api/routes/studies.py`)
- Modify: `tests/test_api_endpoints.py`

**Interfaces:**
- Produces `GET /api/v1/dashboard/studies/{study_uid}/dicom` returning raw decrypted sanitized DICOM Part 10 bytes (`Content-Type: application/dicom`) so Cornerstone3D `wadouri:` renders true 12–16-bit pixel matrices in-browser.
- Produces `GET /api/v1/dashboard/worklist` returning stored anonymized study summaries sorted by triage urgency (`STAT_CRITICAL > ELEVATED > ROUTINE`) + timestamp.
- Produces `GET /api/v1/dashboard/studies/{study_uid}/raw-dicom` (temporary in-session preview for Original `[1]` vs De-Identified `[2]` comparison inside Cornerstone3D, or clean status code `410`/`404` once crypto-shredded).

- [ ] **Step 1: Write failing API tests in `tests/test_api_endpoints.py`**
  - Verify `GET /api/v1/dashboard/studies/{study_uid}/dicom` returns valid `DICM` preamble (`bytes[128:132] == b"DICM"`) and scrubbed PatientName after ingestion.
  - Verify requesting the DICOM stream returns `403` or `410` after `/api/v1/dashboard/shred/{study_uid}` is executed.
- [ ] **Step 2: Run targeted pytest to confirm FAIL**
  - Run: `python -m pytest tests/test_api_endpoints.py -v`
- [ ] **Step 3: Implement backend endpoints & CORS/binary headers**
  - Add `/api/v1/dashboard/studies/{study_uid}/dicom` and `/api/v1/dashboard/worklist` in `medshield/api/routes/dashboard.py`.
  - Ensure `EncryptedStore.load(study_uid)` + `decrypt_envelope(..., _dashboard_kms)` returns clean Part 10 bytes with `preamble = b"\x00" * 128`.
- [ ] **Step 4: Run full pytest suite to verify PASS**
  - Run: `python -m pytest tests/ -v`
  - Expected: All tests pass (`exit code 0`).
- [ ] **Step 5: Local commit**
  - `git add docs/ .claude/ medshield/api/routes/dashboard.py tests/test_api_endpoints.py`
  - `git commit -m "feat(api): add DICOM Part 10 stream and worklist endpoints for Cornerstone3D"`

---

### Phase 3: Design System & Token Generation

#### Task 3: Generate Tokens, `.interface-design/system.md`, and Tailwind Integration
**Skills:** `/ui-ux-pro-max`, `/interface-design`, `/design-system`
**Files:**
- Modify: `.interface-design/system.md`
- Create: `frontend/tokens.json`
- Create: `frontend/src/styles/tokens.css`

- [ ] **Step 1:** Run `ui-ux-pro-max` searches for React + shadcn + dark medical dashboards:
  ```powershell
  python .agents/skills/ui-ux-pro-max/scripts/search.py "medical imaging radiology PACS dark" --design-system --variance 5 --motion 4 --density 9 -p "MedShield-AI" -f markdown
  python .agents/skills/ui-ux-pro-max/scripts/search.py "accessible dialog slider table" --stack shadcn
  ```
- [ ] **Step 2:** Create `frontend/tokens.json` mapping 3-layer tokens (`primitive` $\to$ `semantic` $\to$ `component`) strictly matching `.interface-design/system.md` (`#0C0E13`, `#13161D`, `#1A1D26`, `#0F1117`, `#E8E9ED`, `#A0A5B1`, `#787D8A`, `#34D399`, `#FBBF24`, `#F87171`, `#60A5FA`).
- [ ] **Step 3:** Generate `frontend/src/styles/tokens.css`:
  ```powershell
  node .agents/skills/design-system/scripts/generate-tokens.cjs --config frontend/tokens.json -o frontend/src/styles/tokens.css
  ```
- [ ] **Step 4:** Local commit of tokens and updated `system.md`.

---

### Phase 4: Build React + TypeScript + Cornerstone3D + shadcn/ui Application

#### Task 4: Scaffold `frontend/` with Vite + Cornerstone3D + shadcn/ui + Zustand
**Skills:** `/ui-styling`
**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`, `frontend/tsconfig.app.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/components.json`
- Create: `frontend/src/index.css`
- Create: `frontend/src/lib/initCornerstone.ts`

- [ ] **Step 1:** Scaffold React + TypeScript Vite app inside `frontend/`:
  ```powershell
  npm create vite@latest frontend -- --template react-ts
  npm --prefix frontend install @cornerstonejs/core @cornerstonejs/tools @cornerstonejs/dicom-image-loader dicom-parser zustand lucide-react clsx tailwind-merge
  npm --prefix frontend install -D @originjs/vite-plugin-commonjs tailwindcss @tailwindcss/vite
  ```
- [ ] **Step 2:** Initialize `shadcn/ui` inside `frontend/` (`npx shadcn@latest init`) configured to reference semantic CSS variables from `tokens.css`, and add only needed accessible Radix primitives:
  `button`, `badge`, `tabs`, `slider`, `select`, `table`, `alert-dialog`, `tooltip`, `sonner` (for non-blocking toasts).
- [ ] **Step 3:** Write `frontend/vite.config.ts` with mandatory Cornerstone3D config (`viteCommonjs()`, `worker: { format: 'es' }`, `optimizeDeps.exclude: ['@cornerstonejs/dicom-image-loader']`, `optimizeDeps.include: ['dicom-parser']`, and `server.proxy['/api'] = 'http://127.0.0.1:8000'`).
- [ ] **Step 4:** Write `frontend/src/lib/initCornerstone.ts` exporting an idempotent `initCornerstone()` async bootstrapper (registers `WindowLevelTool`, `ZoomTool`, `PanTool`, and mouse wheel bindings in a ToolGroup).
- [ ] **Step 5:** Run `npm --prefix frontend run build` and verify clean compile (`exit code 0`).

---

#### Task 5: Typed API Client & Zustand Stores
**Files:**
- Create: `frontend/src/types/clinical.ts`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/stores/useWorkstationStore.ts`

- [ ] **Step 1:** Define TypeScript contracts in `clinical.ts` matching FastAPI JSON schemas (`AnalyzeResponse`, `PredictionItem`, `SecurityMetrics`, `PiiTagDiff`, `WorklistEntry`).
- [ ] **Step 2:** Implement `safeApiRequest<T>()` in `api.ts` checking `res.ok`, parsing `await res.text()` cleanly to prevent `Unexpected token 'I'` crashes on 500s, and providing typed helpers (`fetchWorklist`, `analyzeSample`, `analyzeUpload`, `cryptoShredStudy`, `buildDicomImageId`).
- [ ] **Step 3:** Build `useWorkstationStore.ts` managing active study, worklist queue, active plane mode (`raw` | `redacted` | `heatmap`), active heatmap pathology, opacity (`0–100`), invert polarity flag, window/level reset trigger, loading state, and error toast triggers.
- [ ] **Step 4:** Run `npx --prefix frontend tsc --noEmit` verifying strict TypeScript checks pass.

---

#### Task 6: Cornerstone3D Reading-Room Viewport + Synchronized Grad-CAM Overlay
**Skills:** `/ui-styling`, `/frontend-design`
**Files:**
- Create: `frontend/src/components/viewer/CornerstoneViewport.tsx`
- Create: `frontend/src/components/viewer/ViewportToolbar.tsx`
- Create: `frontend/src/components/viewer/ViewerTabs.tsx`

- [ ] **Step 1:** Implement `CornerstoneViewport.tsx`:
  - Initializes a single Cornerstone `RenderingEngine` + Stack viewport (`Enums.ViewportType.STACK`).
  - Loads sanitized DICOM directly from `wadouri:/api/v1/dashboard/studies/{uid}/dicom` (or falls back smoothly to raster display only for raw pre-DICOM PNG preview if needed).
  - Wires Cornerstone ToolGroup: Left-drag **Window/Level (WW/WC)**, Middle-drag / Space-drag **Pan**, Right-drag / Wheel **Zoom**, plus keyboard hotkeys (`I` invert colormap `viewport.setProperties({ invert })`, `R`/`0` `viewport.resetCamera()` + `resetProperties()`, `1/2/3` mode switch).
  - Overlays a precision `<img />` or canvas layer for Grad-CAM heatmaps aligned inside the viewport container with smooth opacity (`0–100%`) and radial light-box vignette falloff.
- [ ] **Step 2:** Build `ViewportToolbar.tsx` (floating accessible control dock with target pathology `<Select>`, Grad-CAM Mix `<Slider>`, WW/WC preset buttons e.g. *Lung / Soft Tissue*, *Invert*, *Zoom +/-*, *Reset*).
- [ ] **Step 3:** Verify `npm --prefix frontend run build` succeeds with zero warnings/errors.

---

#### Task 7: Clinical Worklist Rail, Safe Harbor Table, Triage & Crypto-Shred Panels
**Skills:** `/ui-styling`, `/design-system`
**Files:**
- Create: `frontend/src/components/sidebar/IngestionDropzone.tsx`
- Create: `frontend/src/components/sidebar/WorklistRail.tsx`
- Create: `frontend/src/components/audit/SafeHarborTable.tsx`
- Create: `frontend/src/components/diagnostics/TriagePanel.tsx`
- Create: `frontend/src/components/security/EnvelopeInspector.tsx`
- Create: `frontend/src/components/security/CryptoShredDialog.tsx`
- Create: `frontend/src/App.tsx`

- [ ] **Step 1:** Build left rail (`240–260px`): keyboard-accessible drag/drop DICOM+PNG uploader (`IngestionDropzone.tsx`) + AI-prioritized reference cases and live ingested studies (`WorklistRail.tsx`).
- [ ] **Step 2:** Build lower center panel: `SafeHarborTable.tsx` using shadcn `<Table>` displaying tag hex, attribute, raw PHI vs scrubbed value, burned-in pixel redaction badge, and HIPAA compliance badge.
- [ ] **Step 3:** Build right rail (`320px`):
  - `TriagePanel.tsx`: clickable pathology confidence rows + `±` epistemic uncertainty + urgency badge (`STAT_CRITICAL`, `ELEVATED`, `ROUTINE`) that switch the active Grad-CAM target on click.
  - `EnvelopeInspector.tsx`: Shannon entropy progress meter toward `8.00 bits/byte`, click-to-copy SHA-256 digest button, `MEDENC01` 64-byte wire header monospace viewer.
  - `CryptoShredDialog.tsx`: accessible Radix `<AlertDialog>` (plus inline confirmation) triggering `POST /api/v1/dashboard/shred/{uid}` and showing verified erasure state.
- [ ] **Step 4:** Validate all component styles use design tokens only:
  ```powershell
  node .agents/skills/design-system/scripts/validate-tokens.cjs --dir frontend/src/
  npm --prefix frontend run build
  ```
- [ ] **Step 5:** Local commit of full `frontend/` codebase.

---

### Phase 5: Live Browser Verification, Visual Audit & Production Wiring

#### Task 8: Playwright E2E Testing, Visual Inspection & Verification Gate
**Skills:** `/webapp-testing`, `/verification-before-completion`
**Files:**
- Create: `tests/verify_frontend_e2e.py` (or temporary Playwright script in scratch directory)
- Modify: `medshield/api/app.py` (optional static mount of `frontend/dist` at `/app` or `/` when built, preserving API routes)

- [ ] **Step 1:** Install Playwright Chromium if absent (`pip install playwright && playwright install chromium`).
- [ ] **Step 2:** Inspect `with_server.py --help` (`python .agents/skills/webapp-testing/scripts/with_server.py --help`) and launch both servers simultaneously (use `BypassSandbox: true` on Windows if external browser sockets require it):
  - Backend: `python -m uvicorn medshield.api.app:app --host 127.0.0.1 --port 8000`
  - Frontend: `npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173`
- [ ] **Step 3:** Run Playwright E2E script testing all critical flows:
  1. Wait for `networkidle`, assert zero `console.error` / uncaught `pageerror` exceptions.
  2. Assert desktop (`1440×900`) and mobile (`390×844`) layouts render without horizontal overflow or overlapping docks.
  3. Click Patient 01 (`patient_01_pneumonia`), verify non-empty Cornerstone3D `<canvas>` bounding box & pixel buffer rendered, verify 11 scrubbed DICOM Safe Harbor rows, verify Shannon entropy $\ge 7.99$.
  4. Upload `test_samples/patient_02_effusion.dcm` via file input chooser, switch between `Original`, `De-Identified`, and `Grad-CAM` modes, drag Heatmap Mix slider, click `Cardiomegaly` pathology row, trigger Invert (`I`).
  5. Execute DPDP Section 12 Crypto-Shredding on Patient 01 via the AlertDialog, verify confirmation toast & UI state, then load Patient 03 confirming multi-study key isolation.
  6. Capture PNG screenshots (`desktop_loaded.png`, `gradcam_active.png`, `mobile_stacked.png`) and inspect each image via `read_file`.
- [ ] **Step 4:** Execute `/verification-before-completion` checklist:
  - Run `python -m pytest tests/ -v` (confirm all pass).
  - Run `npm --prefix frontend run build` (confirm `exit code 0`).
  - Run `tests/verify_frontend_e2e.py` (confirm all assertions pass after final edit).
  - Commit final verified changes locally (**DO NOT run `git push`**).
