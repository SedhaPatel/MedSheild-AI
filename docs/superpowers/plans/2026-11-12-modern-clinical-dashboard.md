# Modern Clinical Diagnostic & Security Dashboard (Option B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the MedShield-AI web dashboard into a hospital-grade, error-resilient clinical workstation UI using modern Tailwind CSS, Lucide Icons, interactive PACS canvas tools (Zoom, Pan, Window-Leveling, Opacity Slider), and non-blocking floating toast notifications (eliminating all crude `alert()` boxes).

**Architecture:** Embed a modern single-page application served directly from FastAPI (`/dashboard` and `/`), utilizing Tailwind CSS 3.x CDN, Lucide SVG icons, and a defensive JavaScript client layer with full error boundaries, study-isolated cryptographic envelope keys, and real-time Grad-CAM opacity blending.

**Tech Stack:** FastAPI (Backend), Tailwind CSS 3.x, Lucide Icons, Plus Jakarta Sans & JetBrains Mono fonts, TorchXRayVision (DenseNet-121), AES-256-GCM (`MEDENC01`), HTML5 Canvas API.

**Spec:** [SPEC.md](file:///d:/ISC-Project/SPEC.md)

---

## Global Constraints

- Zero external node/npm build dependencies required by the user — dashboard loads immediately via browser at `http://localhost:8000/dashboard`.
- No raw browser `alert()` popups anywhere — all status, success, and error messages must use animated floating toasts with actionable error summaries.
- Defensive API communication: Client must check `res.ok`, parse raw text safely before JSON conversion, and gracefully handle server errors without crashing.
- Cryptographic isolation: Crypto-shredding must target only the specific study's KEK, never breaking active ingestion for subsequent uploads.
- Full DICOM & PNG compatibility: Must support drag-and-drop for `.dcm`, `.png`, `.jpg`, and pre-packaged sample cases.

---

## Review Focus & Error Prevention Matrix

1. **Non-JSON Server Errors:** When a server responds with 500 or non-JSON payload, `res.json()` throws `SyntaxError: Unexpected token 'I', "Internal S"...`. The client must read `await res.text()` first, attempt JSON decode, and fallback to text error extraction.
2. **Crypto-Shredding Blast Radius:** Revoking Master KEK previously broke all subsequent uploads. Fix: Study-level isolated KEKs (`{master_kek_id}:{study_uid}`).
3. **Large File Upload Freezing:** Show responsive spinner overlay with step-by-step progress feedback (Sanitizing $\to$ Encrypting $\to$ Deep Learning $\to$ Grad-CAM).
4. **Grad-CAM Opacity & Window-Leveling:** Radiologists need to adjust heatmap transparency to inspect underlying lung parenchyma. Provide real-time opacity slider (`0%` to `100%`) and contrast filters.
5. **Memory Leakage:** Clean up base64 image object URLs and canvas contexts on every new study load.

---

## Planned File Structure

- `medshield/api/routes/dashboard.py`: Contains API endpoints (`/api/v1/dashboard/analyze`, `/api/v1/dashboard/samples`, `/api/v1/dashboard/shred/{study_uid}`) and the modern Tailwind SPA HTML/JS.
- `medshield/api/middleware/mtls_auth.py`: Ensures browser bypass for dashboard endpoints without security holes on clinical API routes.
- `tests/test_api_endpoints.py`: Automated pytest test covering dashboard HTML, sample listing, and defensive error handling.

---

## Step-by-Step Task Breakdown

### Task 1: Defensive Backend Hardening & Study-Level Key Isolation
- [ ] Fix KEK isolation in `medshield/api/routes/dashboard.py` so each study uses `f"{settings.kms_master_key_id}:{study_uid}"`.
- [ ] Ensure `demo_crypto_shredding` revokes only that study's key, preserving active ingestion.
- [ ] Add explicit HTTP error responses with structured JSON error details `{ "error": true, "message": "..." }`.

### Task 2: Modern Dark Workstation UI with Tailwind CSS & Lucide Icons
- [ ] Incorporate Tailwind CSS 3.x and Lucide Icons via high-availability CDNs.
- [ ] Implement hospital-grade medical console aesthetic: deep slate obsidian (`#0b0f19`), ice-blue borders (`#1e293b`), clinical cyan accents (`#06b6d4`).
- [ ] Implement top clinical monitor bar with real-time status badges (KMS Provider, TorchXRayVision Model, FIPS 140-3, HIPAA/DPDP).

### Task 3: Interactive PACS Canvas Controls & Grad-CAM Opacity Slider
- [ ] Implement canvas viewer supporting Zoom In/Out, Reset Pan, and Invert/Contrast presets (Lung Window, Bone Window).
- [ ] Add dual-layer image canvas allowing dynamic Grad-CAM opacity adjustments (`0%` to `100%`) over the de-identified radiograph.
- [ ] Add pathology switcher dropdown triggering real-time re-centering of Grad-CAM activations.

### Task 4: Non-Blocking Floating Toast System & Defensive Client Error Handling
- [ ] Build custom floating toast notification container (`#toast-container`) with slide-in animations.
- [ ] Replace all `alert()` calls with `showToast(title, message, type='error'|'success'|'info')`.
- [ ] Wrap `fetch` calls in defensive response parsers:
  ```javascript
  const text = await res.text();
  let json;
  try { json = JSON.parse(text); } catch { throw new Error(text || 'Server returned invalid response'); }
  if (!res.ok) throw new Error(json.detail || json.message || text);
  ```

### Task 5: Side-by-Side PII Table & Cryptographic Envelope Visualizer
- [ ] Redesign DICOM PS 3.15 tag audit table with search filter and green/red status pills.
- [ ] Add real-time Shannon Entropy Gauge visualizer displaying $H(X)$ with pass/fail threshold ($\ge 7.99$).
- [ ] Add 1-click SHA-256 and study UID clipboard copy buttons.
- [ ] Add modal confirmation for DPDP Section 12 Crypto-Shredding with animated shred feedback.

### Task 6: Testing & End-to-End Verification
- [ ] Run pytest suite ensuring 29/29 tests pass.
- [ ] Run standalone upload verification script against live server on port 8000.
- [ ] Test browser ingestion with both pre-packaged samples and direct file drag-and-drop.

