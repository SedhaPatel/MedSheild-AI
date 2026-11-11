# MedShield-AI Clinical PACS Workstation (Option 1) — Frontend Design Spec

**Date:** 2026-11-12  
**Target Stack:** React 19 + TypeScript + Vite + Cornerstone3D (WebGL/Wasm) + Tailwind CSS + shadcn/ui (Radix) + Zustand  
**Companion Backend:** FastAPI (`medshield/api/`)

---

## 1. Product Vision & Users
MedShield-AI is a zero-trust thoracic radiography platform bridging clinical radiology triage with HIPAA Privacy/Security compliance and India DPDP Act 2023 controls.

Primary users:
1. **Emergency / ICU Radiologist:** Opens flagged chest radiographs sorted by clinical urgency, inspects raw vs. scrubbed studies with smooth Window Width / Window Center (WW/WC) adjustments, zooms/pans lesions, and cross-checks explainable Grad-CAM heatmaps.
2. **Clinical Security Officer / Compliance Auditor:** Verifies HIPAA Safe Harbor (18 identifiers + burned-in pixel PHI OCR redaction), confirms FIPS 140-3 AES-256-GCM envelope randomness (`H >= 7.99 bits/byte`) + SHA-256 integrity, and demonstrates DPDP Section 12 per-study Crypto-Shredding.

---

## 2. Benchmark Principles (From PACS & Radiology AI Best Practices)
Grounded in OHIF Viewer, Cornerstone3D, and clinical triage workstations:
- **Tri-zone diagnostic hierarchy:** AI-prioritized worklist on the left, dominant reading-room DICOM viewport in the center, quantitative pathology + security verification on the right.
- **Native 12–16-bit DICOM pixel viewing:** Cornerstone3D loads sanitized Part 10 DICOM instances over `wadouri:` into WebGL viewports so clinicians get continuous mouse-drag Window/Level, presets (*Default*, *Lung*, *Bone / Soft*), zoom/pan, and polarity invert (`I`).
- **Non-intrusive Explainable AI (XAI):** Grad-CAM saliency layers align cleanly over the viewport canvas, toggle on/off (`1`/`2`/`3` modes), and blend smoothly via a `0%–100%` opacity slider without darkening or obscuring original lung markings. Epistemic uncertainty (`±0.0xx`) accompanies every score.
- **Keyboard-first low-click workflow:** Minimal steps to switch scan planes (`1` Original PNG/DICOM, `2` De-Identified DICOM via Cornerstone3D, `3` Grad-CAM overlay), adjust pathology focus by clicking rows in Diagnostic Triage, `I` to invert, `+`/`-`/`0` for zoom/reset, and non-blocking toasts instead of browser modal alerts.

---

## 3. Core Workstation Architecture

### 3.1 Spatial Layout (Desktop `>= 1024px`)
- **Top Bar (`44px` height):** App identity, active study UID pill, modality badge, encryption/compliance status pills, and direct API link.
- **Left Rail (`256px` fixed): Study Ingestion & AI Triage Worklist**
  - Drag-and-drop `.dcm` / `.png` / `.jpg` upload dropzone (keyboard & ARIA accessible).
  - Pre-packaged reference clinical cases (`Patient 01: Pneumonia`, `Patient 02: Effusion`, `Patient 03: Cardiomegaly`).
  - Dynamic **Session Worklist Queue** recording studies ingested in this session sorted by clinical urgency (`STAT_CRITICAL` > `ELEVATED` > `ROUTINE`).
- **Center Stage (Fluid, `>= 60%` remaining space): Reading-Room Viewport + Safe Harbor Diff Drawer**
  - Plane switcher tabs: `Original [1]`, `De-Identified (Cornerstone3D) [2]`, `Grad-CAM [3]`.
  - Floating bottom dock overlay (visible on hover, focus-within, and touch): Window/Level tool toggle, Pathology target selector, Grad-CAM Mix slider (`0%–100%`), Film Invert (`I`), Zoom (`+`/`-`), Reset (`0`).
  - Lower collapsible/resizable **DICOM PS 3.15 Safe Harbor Audit Matrix** comparing pre-ingestion raw PHI against post-ingestion pseudonymized/scrubbed attributes plus burned-in pixel redaction status.
- **Right Rail (`320px` fixed): Triage, Encryption & Erasure**
  - **Diagnostic Triage:** Inference latency + clickable 5-pathology confidence bars (`Pneumonia`, `Cardiomegaly`, `Pleural Effusion`, `Pneumothorax`, `Atelectasis`) + epistemic uncertainty.
  - **Envelope Storage (`AES-256-GCM`):** Shannon entropy meter (`H >= 7.99` target badge), clickable SHA-256 digest copy control, and 64-byte `MEDENC01` binary wire header preview.
  - **DPDP Act Sec. 12 Right to Erasure:** Accessible Radix `<AlertDialog>` confirming permanent key destruction for the active study UID while leaving sibling studies readable.

---

## 4. Non-Goals & Anti-Patterns Rejected
- No Streamlit widgets or full-page reloads.
- No multi-column card mosaic where metadata cards shrink the radiograph viewport.
- No neon cyber glow/drop-shadow decoration or rainbow text gradients.
- No browser `alert()`, `confirm()`, or unguarded `res.json()` calls on error payloads.

