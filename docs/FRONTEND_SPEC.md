# MedShield-AI: Clinical Portal & Zero-PII Scan Chat Specification

**Document ID:** `FRONTEND_SPEC.md`  
**Status:** Updated & Approved for Planning (Brainstormed Architecture)  
**Frontend Stack:** React 19 + TypeScript + Vite + Cornerstone3D + Tailwind CSS v4 + Radix UI + Zustand  
**Companion Backend:** FastAPI (`medshield/api/`)  
**Reference Visual System:** [`.interface-design/system.md`](file:///d:/ISC-Project/.interface-design/system.md) & [`frontend/tokens.json`](file:///d:/ISC-Project/frontend/tokens.json)

---

## 1. Visual Identity & Unchanged Portal Template

The UI preserves the **Daylight Evidence-First Clinical Portal** aesthetic across all routes—**no dark backgrounds, no glowing text (`text-shadow: none !important`), and no neon colors**:

| Role | Token (`tokens.json`) | Exact Value | Usage |
| :--- | :--- | :--- | :--- |
| Base Canvas | `--bg-canvas` | `#F8FAFC` | Porcelain alabaster page background & drawer messages |
| Primary Panels | `--bg-panel` | `#FFFFFF` | Cards, navigation header, PACS rails, slide-over chat sheet |
| Inset Inputs | `--bg-input` | `#F8FAFC` | Form inputs, drawer header/footer, table stripe alternation |
| Alternating Band | `--bg-tint` | `#F2F8F6` | "How It Works" band on `/` |
| Viewport Lightbox | `--bg-lightbox` | `#EEF3F8` | Cornerstone3D canvas clear color `[0.933, 0.953, 0.973]` |
| Modal Backdrop | `--bg-backdrop` | `rgba(241, 245, 249, 0.82)` | Frosted light overlay for dialogs & slide-over chat sheet |
| Primary / Muted Ink | `--text-primary` / `--text-muted` | `#1E293B` / `#64748B` | Matte high-contrast clinical typography (`Figtree`, `Noto Sans`, `IBM Plex Mono`) |
| Brand & Verification | `--accent-brand` / `--accent-teal` | `#0284C7` / `#0F766E` | Cerulean primary CTAs, user bubbles, surgical teal Zero-PII badges |
| Status Accents | `--accent-verified` / `--accent-attention` / `--accent-critical` | `#047857` / `#B45309` / `#B91C1C` | Matte Safe Harbor, moderate confidence, and STAT/shredded states |

---

## 2. Multi-Page Clinical Portal Structure

1. **`/` — Identifier Hub (`OverviewPage.tsx`):**
   - Centered daylight editorial hero + **uncluttered 2-card interactive workbench**:
     - **Card 1 (`1. Radiograph Input & Clinical Context`):** `.dcm` / `.png` / `.jpg` dropzone + `Ctrl+V` clipboard paste, capture framing tip, target pathology selector, care setting context pills, optional notes, and validated reference sample triggers.
     - **Card 2 (`2. Diagnostic Evidence & Safety Report`):** Scrubbed chest radiograph + Grad-CAM preview toggle, top pathology score + epistemic uncertainty (`±0.0xx`), visible radiographic cues, differential lookalikes, 4 alternative disease bars, Safe Harbor + entropy pills, navigation CTAs (`PACS Viewer`, `Security Vault`, `Worklist`), and the single **`"Ask AI About This Scan"`** entry button for scan chat.
   - Alternating lower bands: **How Zero-Trust Study Identification Works** (4 numbered cards), **Thoracic Pattern Reference & Differential Lookalikes**, and **Clinical Decision-Support Scope** footer.
2. **`/worklist` — Worklist Queue (`WorklistPage.tsx`):** Triage-prioritized session queue (`STAT_CRITICAL > ELEVATED > ROUTINE`), filter pills, search input, dropzone, and direct Inspect/Audit row actions.
3. **`/workstation` — PACS Reading Room (`WorkstationPage.tsx`):** Full-focus Cornerstone3D WebGL viewport (`Original [1]`, `De-Identified DICOM [2]`, `Grad-CAM [3]`), W/L, Pan, Invert, Zoom, Reset, interactive Diagnostic Triage rail, plus optional secondary **`"Ask AI About This Scan"`** trigger reusing the same drawer component.
4. **`/security` — Security & Audit Vault (`SecurityAuditPage.tsx`):** Side-by-side raw vs. pixel-redacted comparison, full 18-tag DICOM PS 3.15 Safe Harbor matrix, AES-256-GCM Shannon entropy meter (`>= 7.99 bits/byte`), SHA-256 & 64-byte `MEDENC01` hex preview, and two-step DPDP Act Sec. 12 Crypto-Shredding dialog.

---

## 3. Feature Addition: Minimal UI "Chat About This Scan"

### 3.1 UI Placement & Visual Discipline
To preserve the clean 2-card dashboard without compressing Card 1/Card 2 heights or adding permanent chat chrome:

1. **Single Trigger Button Inside Card 2 Header (`OverviewPage.tsx` Results Card):**
   - Place one uncluttered `<Button variant="soft" size="sm">` labeled **`Ask AI About This Scan`** inside the Card 2 header utility bar (to the left of the confidence badge, rendered cleanly in both pre-upload and post-upload states).
   - Disabled gracefully with accessible Radix Tooltip when `!activeStudy` (`"Upload or select a scan first"`) or when the active `scan_id` has been crypto-shredded (`"Study erased under DPDP Sec. 12"`).
   - Clicking opens a **Daylight Slide-Over Drawer** (`<ScanChatDrawer />` mounted inside `<BrowserRouter>` in `App.tsx`, also optionally triggered from `WorkstationPage.tsx`). When `chatOpen === true`, global reading hotkeys (`1`/`2`/`3`/`I`/`+`/`-`/`0`) in `App.tsx` are muted.

2. **Slide-Over Drawer (`ScanChatDrawer.tsx` — Built on `@radix-ui/react-dialog`):**
   - **Dimensions:** Fixed right sheet (`width: 420px` on desktop `>= 640px`, `width: 100vw` max sheet on mobile), `h-full`, `bg-bg-panel` (`#FFFFFF`), left boundary `1px solid var(--border-strong)`, frosted backdrop `bg-bg-backdrop backdrop-blur-xs`, zero dark shadow or text glow.
   - **Drawer Header (`bg-bg-input`):**
     - Title: `Ask AI About This Scan` (`font-display text-sm font-semibold text-text-primary`)
     - Verified privacy pill (`Badge variant="teal"`): `Zero-PII Verified` (locks confirmation that only PS 3.15 scrubbed image + classifier output leave local enclave)
     - Compact study context pill (`font-mono text-[11px]`): top pathology + score (e.g., `Pleural Effusion • 42.1% (±0.044)`) + anonymous short UID.
     - Accessible Close (`X`) button (`focus-visible:outline-2 focus-visible:outline-border-focus`).
   - **Persistent Clinical Scope Banner:**
     - Subtle matte ochre alert bar (`bg-accent-attention-soft border-accent-attention-border text-accent-attention`): *"AI explanations reflect anonymized model outputs only and do not establish a clinical diagnosis."*
   - **Scrollable Conversation Thread (`bg-bg-panel`):**
     - **Initial Empty State + 3 Quick-Question Chips (`rounded-full border border-border-strong bg-bg-canvas hover:bg-bg-elevated`):**
       1. `"Explain this finding in simple terms"`
       2. `"What did the heatmap highlight?"`
       3. `"Next recommended clinical steps"`
     - Clicking any chip immediately submits that prompt (`POST /api/chat`), hides/collapses the starter card smoothly or keeps chips accessible as 1-line suggestions until user replies.
     - **Message Bubbles:**
       - User bubble: right-aligned, max-width `85%`, `bg-accent-brand-soft border border-accent-brand-border text-text-primary`, `rounded-[var(--panel-radius)]`.
       - Assistant bubble: left-aligned, max-width `92%`, `bg-bg-canvas border border-border-subtle text-text-primary`, renders structured paragraphs cleanly plus collapsible/compact grounded chip footer (e.g. `Grounded: DenseNet-121 • Zero-PII Checked`) and provider badge (`Gemini` / `MedGemma` / `Offline Fallback`).
     - **Loading, Erasure & Transport States:**
       - Uses standard **synchronous JSON REST (`POST /api/chat`)**; while pending, shows a non-blocking matte typing indicator inside the thread and prevents duplicate submits.
       - Frontend `safeApiRequest` throws typed `ApiError(message, status)` so **`HTTP 410 Gone`** (DPDP Sec. 12 crypto-shredded) is caught cleanly by status code and displays a crisp crimson inline notice inside the drawer.
   - **Frontend State vs. Wire Type Contract:**
     - Client UI thread stores `ScanChatMessage[]` (`id`, `role: 'user' | 'assistant' | 'system'`, `content`, `provider_used?`, `grounded_findings?`, `timestamp`, `isError?`).
     - Before `POST /api/chat`, `conversation_history` is mapped strictly to `ScanChatTurn[]` (`{ role: 'user' | 'assistant', content: string }`), filtering out `system` notices and capping to the most recent `6` turns.
   - **Composer Footer (`bg-bg-input border-t border-border-subtle`):**
     - Single-row auto-growing `<textarea>` (`maxlength=1500`) + Send button (`variant="primary"`).
     - **IME-Safe Enter Handling (`ui-ux-pro-max`):** `Enter` (without `Shift`/`Ctrl`/`Meta`) guards `if (e.isComposing || e.keyCode === 229) return` before submitting; `Shift+Enter` inserts newline.
     - Reminder micro-caption (`10px text-text-muted`): `"Do not enter patient names, DOBs, or MRNs. Accidental identifiers are stripped before model egress."`

---

## 4. Backend API & Security Contract (`/api/chat`)

### 4.1 Route & Middleware Parity
- **Primary Route:** `POST /api/chat` (plus alias `POST /api/v1/dashboard/chat` reusing the identical FastAPI handler).
- **Middleware (`medshield/api/middleware/mtls_auth.py`):** Explicitly exempt `/api/chat` alongside `/api/v1/dashboard` so local browser SPA requests do not fail mTLS header enforcement while core STOW-RS/DICOMweb routes remain protected.
- **Vite Proxy:** `frontend/vite.config.ts` already proxies all `/api/*` requests to `http://127.0.0.1:8000`.

### 4.2 Request & Response Schema

**`POST /api/chat` Request (`ScanChatRequest`):**
```json
{
  "scan_id": "2.25.7093991301889367304617530439374403004898731214931828136692",
  "user_message": "What did the heatmap highlight?",
  "target_pathology": "Pneumonia",
  "include_heatmap_overlay": true,
  "conversation_history": [
    { "role": "user", "content": "Explain this finding in simple terms" },
    { "role": "assistant", "content": "..." }
  ]
}
```
> Notes:
> - Client does **not** pass raw DICOM images or mutable disease probabilities as authoritative truth. When `scan_id` resolves an encrypted `.enc` envelope on disk, the backend treats the decrypted scrubbed image + `InferenceEngine` predictions as single source of truth.
> - **Heatmap Grounding (`include_heatmap_overlay`):** Frontend sets `include_heatmap_overlay: true` automatically whenever the Grad-CAM preview toggle (`previewHeatmap`) or PACS `heatmap` tab is active, OR when Quick Question #2 (`"What did the heatmap highlight?"`) / `"heatmap"` is asked. When `true`, the backend generates the scrubbed Grad-CAM blended image (`_dashboard_engine.generate_heatmap_image(cleaned_ds, valid_pathology)`) + computes the spatial lung quadrant peak label cleanly from the activation map, supplying the scrubbed heatmap overlay image cleanly so Gemini / MedGemma inspect the actual localized activation without guessing.

**`POST /api/chat` Response (`ScanChatResponse`):**
```json
{
  "scan_id": "2.25.7093991301889367304617530439374403004898731214931828136692",
  "provider_used": "gemini-2.5-flash",
  "answer": "The classifier estimates Pleural Effusion at 42.1% (±0.044) with ROUTINE urgency...",
  "grounded_findings": [
    "Pleural Effusion: 42.1% (±0.044, ROUTINE)",
    "Cardiomegaly: 26.4% (±0.033, ROUTINE)"
  ],
  "zero_pii_verified": true,
  "pii_redacted_from_prompt": false,
  "medical_disclaimer": "Decision-support summary only. Verify findings with a qualified radiologist and clinical history."
}
```

### 4.3 Five-Layer Zero-PII Protection Boundary

1. **Forbidden Cache Isolation:** `_dashboard_session_cache` retains `pre_pii_tags` and `raw_image_data_url` solely for the `/security` audit diff UI. `/api/chat` **MUST NEVER** read `_dashboard_session_cache`.
2. **Envelope-Only Decryption + DPDP Sec. 12 Gate:** `/api/chat` loads `store.load(scan_id)` (`404` if unknown) and decrypts in RAM via `decrypt_envelope(enc_blob, _dashboard_kms)`. If the study Master KEK was shredded, decryption raises and returns **`HTTP 410 Gone`**, halting chat immediately.
3. **Runtime Pre-Egress Compliance Gate (`ComplianceScanner`):** Runs `ComplianceScanner().scan_dataset(cleaned_ds)` (`is_compliant == True`, raising `HTTP 422` if any HIPAA identifier remains) and verifies `getattr(cleaned_ds, "BurnedInAnnotation", None) == "NO"` before rendering a downscaled RGB PNG (`max 768×768`) solely from scrubbed `PixelData`—zero DICOM metadata attributes are serialized into the VLM prompt.
4. **Prompt Egress PII Scrubber (`redact_chat_pii`):** Scans `user_message` and `conversation_history` (capped to last `6` turns) to mask accidental typed patterns (MRNs, SSN-like IDs, DOB strings, phone numbers, email addresses) with `[REDACTED_PII]` before invoking any external model API.
5. **Strict System Grounding Prompt:** Constrains Gemini / MedGemma to explain **only** the scrubbed radiograph and the exact JSON probability/uncertainty list computed by DenseNet-121, forbidding fabricated lab values, demographic assumptions, or autonomous diagnostic claims, and always returning `medical_disclaimer`.

### 4.4 VLM Provider Adapter (`Gemini Multimodal API` & `google/medgemma-1.5-4b-it`)
Implemented via asynchronous `httpx.AsyncClient` (already in [`requirements.txt`](file:///d:/ISC-Project/requirements.txt)—zero heavy client SDK dependencies):
- **Configuration (`medshield/config.py`):**
  - `MEDSHIELD_CHAT_PROVIDER`: `"gemini"` (default when `GEMINI_API_KEY` is set) or `"medgemma"` (`google/medgemma-1.5-4b-it` via HuggingFace Router / Inference API when `HF_API_TOKEN` is set).
  - `MEDSHIELD_GEMINI_MODEL`: `"gemini-2.5-flash"`
  - `MEDSHIELD_MEDGEMMA_MODEL`: `"google/medgemma-1.5-4b-it"`
  - `MEDSHIELD_CHAT_TIMEOUT_SEC`: `25.0`
- **Offline Deterministic Grounded Fallback:** If neither `GEMINI_API_KEY` nor `HF_API_TOKEN` is configured (or upstream network fails cleanly), returns a structured `"grounded-local-fallback"` answer built directly from the DenseNet-121 probabilities, epistemic uncertainty bounds, and radiology cues + clinical disclaimer so testing and offline PACS deployments never break.

