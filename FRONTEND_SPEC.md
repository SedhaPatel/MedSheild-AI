# MedShield-AI: Clean Frontend Specification & Architecture
**Document ID:** `FRONTEND_SPEC.md`  
**Status:** Approved for Implementation (Design / Spec Phase)  
**Methodology:** Progressive Disclosure Minimalist PACS & UI/UX Pro Max  
**Reference Design System:** `.interface-design/system.md`  

---

## 1. Executive Summary & Design Principles

The objective is to eliminate visual clutter, cognitive overload, and technical noise from the clinical interface. Medical practitioners, radiologists, and researchers need immediate clinical diagnostic clarity and cryptographic assurance without navigating dense multi-column sidebars, fake graphs, or unnecessary settings menus.

### Core Design Rules (Strict Minimalism)
1. **Zero Clutter:** No sidebars, no fake analytics dials, no noisy secondary widgets.
2. **Progressive Disclosure:**
   - **Pre-Upload (Initial State):** A serene, focused upload canvas inviting the user to drop an X-ray or click a sample patient.
   - **Post-Upload (Active State):** Exactly **two clean cards side-by-side**:
     - **Left Card:** High-contrast medical scan with a single toggle switch for *"Show AI Heatmap"*.
     - **Right Card:** Immediate clinical conclusion (Top AI disease finding + confidence bar) and a compact security badge with a collapsed drawer for technical/audit details.
3. **No Crude Dialogs:** All notifications use non-blocking, accessible floating toasts. Zero browser `alert()` popups.
4. **Instant Actionability:** One primary button to download the decrypted scan, with an optional one-click cryptographic shredder (India DPDP Act right to erasure).

---

## 2. Backend API Endpoint & JSON Parity Matrix

The frontend integrates directly with the existing MedShield-AI FastAPI endpoints with 100% schema alignment:

### 2.1 Endpoint Specification

| Method | Endpoint | Request Payload | Response Object | UI Consumer Component |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/dashboard/samples` | None | `{"samples": [...]}` | Quick-load clinical case chips |
| `POST` | `/api/v1/dashboard/analyze` | `FormData`: `file` or `sample_id`, `pathology_heatmap` | `DashboardAnalysisResponse` (JSON) | Left & Right Cards |
| `POST` | `/api/v1/dashboard/shred/{study_uid}` | URL path parameter | `{"status": "CRYPTO_SHREDDED", ...}` | Cryptographic Shred trigger |
| `GET` | `/api/v1/dashboard/download/{study_uid}` | URL path parameter | Binary stream (`image/png` or `.dcm`) | "Download Decrypted Scan" button |

### 2.2 Complete JSON Response Schema (`/api/v1/dashboard/analyze`)

```json
{
  "status": "SUCCESS",
  "file_name": "patient_01_pneumonia.dcm",
  "anonymous_study_instance_uid": "2.25.7093991301889367304617530439374403004898731214931828136692",
  "security": {
    "encryption_algorithm": "AES-256-GCM Envelope Encryption",
    "container_magic_header": "MEDENC01",
    "kms_master_key_id": "arn:medshield:kms:local:key/master-kek-v1:2.25...",
    "storage_file_path": "storage/encrypted_studies/...",
    "storage_file_size_bytes": 195456,
    "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "shannon_entropy_bits_per_byte": 7.99937,
    "entropy_target": ">= 7.99000",
    "hex_preview_64b": "4d 45 44 45 4e 43 30 31 ...",
    "is_tamper_resistant": true,
    "dpdp_crypto_shredding_ready": true
  },
  "deidentification": {
    "burned_in_text_redacted": false,
    "safe_harbor_compliance": "100% COMPLIANT",
    "uid_root": "2.25 (Private Pseudonymized Root)",
    "tag_diff_matrix": [
      {
        "tag_hex": "(0010,0010)",
        "tag_name": "PatientName",
        "description": "Patient Full Name",
        "original_value": "DOE^JOHN",
        "sanitized_value": "ANON_4B12",
        "status": "SANITIZED"
      }
    ]
  },
  "ai_diagnostics": {
    "model_name": "DenseNet-121 (TorchXRayVision NIH / CheXpert)",
    "is_real_weights": true,
    "weights_source": "TorchXRayVision",
    "inference_latency_ms": 38.5,
    "overall_triage_urgency": "ELEVATED",
    "active_heatmap_pathology": "Pneumonia",
    "predictions": [
      {
        "pathology": "Pneumonia",
        "probability": 0.8124,
        "triage_urgency": "ELEVATED"
      },
      {
        "pathology": "Infiltration",
        "probability": 0.6541,
        "triage_urgency": "ELEVATED"
      }
    ]
  },
  "images": {
    "raw_image_url": "data:image/png;base64,...",
    "redacted_image_url": "data:image/png;base64,...",
    "gradcam_heatmap_url": "data:image/png;base64,..."
  }
}
```

---

## 3. Screen Layout & Progressive Disclosure Flow

### 3.1 Top Navigation Bar (Fixed 56px)
- **Left:** MedShield-AI Logomark (Clean shield icon) + App Name: `MedShield-AI` with subtle badge `Clinical Console`.
- **Right:** Security Assurance Pill:
  ```html
  <div class="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
    <span>System Secure (AES-256 / TLS 1.3)</span>
  </div>
  ```

---

### 3.2 Main Area: Progressive Disclosure Architecture

```
+---------------------------------------------------------------------------------------+
|  MedShield-AI  [Clinical Console]                 [● System Secure (AES-256 / TLS 1.3)]|
+---------------------------------------------------------------------------------------+
|                                                                                       |
|   +------------------------------------+   +------------------------------------+     |
|   | CARD 1: MEDICAL RADIOGRAPH         |   | CARD 2: DIAGNOSIS & SECURITY       |     |
|   |                                    |   |                                    |     |
|   | [ State A: Drag-and-Drop Box ]     |   | 1. PRIMARY AI PREDICTION           |     |
|   |   - Drop DICOM (.dcm) or PNG       |   |    Pneumonia (Consolidation)       |     |
|   |   - 3 Quick Case Chips             |   |    [==================      ] 81.2%    |     |
|   |                                    |   |    High Confidence • Urgent Triage |     |
|   | [ State B: Loaded Medical Scan ]   |   |                                    |     |
|   |   - High-contrast radiograph stage |   | 2. COMPACT SECURITY BADGE          |     |
|   |   - Toggle Switch:                 |   |    [✓ PII Stripped • AES-256 Enc.] |     |
|   |     (o) Show AI Heatmap (Grad-CAM) |   |                                    |     |
|   |   - (Optional selector if on)      |   | 3. COLLAPSIBLE DRAWER (Default: Off|     |
|   |                                    |   |    ▾ View Stripped DICOM Tags & Hash|    |
|   |                                    |   |    (Clean 18 Safe Harbor Table     |     |
|   |                                    |   |     + SHA-256 Digest Copy)         |     |
|   |                                    |   |                                    |     |
|   |                                    |   | 4. ACTION BUTTONS                  |     |
|   |                                    |   |    [ ↓ Download Decrypted Scan ]   |     |
|   |                                    |   |    [ 🗑 Crypto-Shred (DPDP Act) ]  |     |
|   +------------------------------------+   +------------------------------------+     |
|                                                                                       |
+---------------------------------------------------------------------------------------+
```

---

## 4. Detailed Component Specifications

### 4.1 Card 1 (Left): Image & Upload Stage

#### Empty State (Initial Load)
- **Container:** Rounded-xl border (`#1E2A44`), background `#0E1524`, height `560px`.
- **Drag-Drop Target:** Clean dashed border with cloud upload icon (`lucide-cloud-upload`).
- **Prompt:** `"Drop DICOM (.dcm) or medical scan (.png) here"` with supporting text `"Zero-Trust DICOM PS 3.15 de-identification runs instantly on upload."`
- **Sample Quick-Buttons:** 3 quiet, elegant pill chips beneath the dropzone:
  - `Patient 01 (Pneumonia)`
  - `Patient 02 (Effusion)`
  - `Patient 03 (Cardiomegaly)`

#### Active State (Scan Loaded)
- **Viewer Viewport:** Centered, aspect-ratio preserved `#000000` PACS stage with subtle 1px border.
- **Image Switch:** Shows `images.redacted_image_url` by default. When the toggle is activated, instantly overlays `images.gradcam_heatmap_url`.
- **Heatmap Toggle Control:**
  - Modern iOS/Tailwind style pill switch:
    `[ Toggle Switch ] Show AI Heatmap (Grad-CAM)`
  - When enabled, displays a clean pill selector for the target pathology if the scan contains multiple findings.
  - Optional subtle opacity slider ($20\%$ to $100\%$) displayed neatly inline without cluttering the screen.

---

### 4.2 Card 2 (Right): Clinical Diagnosis & Security Summary

#### Section 1: Primary AI Prediction
- **Focal Headline:** Top pathology finding (e.g. `Pneumonia`, `Cardiomegaly`, `Pleural Effusion`) in large 20px bold white text (`font-sans font-bold text-white`).
- **Confidence Bar:** A sleek progress track (`#162035`) with animated fill (`#06B6D4` $\rightarrow$ `#3B82F6`):
  - Number callout: `81.2% Probability` (using `tabular-nums` in `JetBrains Mono`).
  - Triage Chip: Compact badge showing urgency level:
    - `ROUTINE` (Emerald chip: `#10B981`)
    - `ELEVATED` (Amber chip: `#F59E0B`)
    - `STAT_CRITICAL` (Rose chip: `#EF4444`)
- **Secondary Predictions (Subtle Progressive Disclosure):**
  - Collapsible or single-line secondary findings summary (e.g., *Other findings: Infiltration 65.4%, Effusion 18.2%*).

#### Section 2: Compact Security Badge
- Clean, compact badge displayed right below diagnosis:
  ```html
  <div class="flex items-center justify-between p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
    <div class="flex items-center gap-2">
      <i data-lucide="shield-check" class="w-4 h-4 text-emerald-400"></i>
      <span class="text-xs font-semibold text-emerald-300">PII Stripped • AES-256-GCM Encrypted</span>
    </div>
    <span class="text-[11px] font-mono text-emerald-400">Entropy 7.999 / 8.0</span>
  </div>
  ```

#### Section 3: Collapsible Drawer ("View Stripped DICOM Tags & Hash")
- **Default State:** Collapsed (`hidden`), keeping the card compact and uncluttered.
- **Trigger:** Accessible accordion button:
  `[ ▾ View Stripped DICOM Tags & Hash ]`
- **Expanded Contents:**
  - **Ciphertext Hash:** 
    - Full SHA-256 string in small `JetBrains Mono` with a 1-click **Copy** icon button.
    - Sealed Container Magic: `MEDENC01 (AES-256-GCM Envelope)`.
  - **DICOM PS 3.15 Stripped Tags Table:**
    - Clean 4-column compact table:
      1. Tag Hex (e.g., `(0010,0010)`)
      2. Tag Name (e.g., `PatientName`)
      3. Pre-Ingestion PHI (e.g., `DOE^JOHN` in soft red)
      4. Post-Ingestion Status (`[ANON_4B12]` or `[SCRUBBED]` in emerald)

#### Section 4: Action Footer
- **Primary CTA:**
  - `[ ↓ Download Decrypted Scan ]` (Primary emerald/cyan button).
  - Triggers direct download of the decrypted, de-identified radiograph (.dcm / .png) for medical review.
- **Secondary Cryptographic Shredding Button:**
  - `[ 🗑 Crypto-Shred Study (DPDP Act) ]`
  - Subtle text/outline button that invokes `/api/v1/dashboard/shred/{study_uid}`.
  - Upon confirmation, updates the badge to `💥 Mathematically Shredded (Zero Key Recovery)`.

---

## 5. Defensive Error Handling & Toast Architecture

1. **No `alert()` Popups:** 
   - All errors, network drops, or invalid file types trigger non-intrusive floating toasts in the top-right corner.
   - Toasts auto-dismiss in 4000ms with a manual dismiss icon.
2. **Safe API Client (`safeApiPost`):**
   - Checks `res.ok` before decoding.
   - Extracts server text via `await res.text()` before `JSON.parse` to eliminate `SyntaxError: Unexpected token 'I', "Internal S"...`.
3. **File Validation:**
   - Client verifies file extension (`.dcm`, `.png`, `.jpg`) before network upload.
   - Files $< 32$ bytes immediately rejected with friendly guidance.

---

## 6. Implementation Readiness Checklist

- [x] Design tokens documented in `.interface-design/system.md`.
- [x] Backend API endpoints and JSON keys fully inspected and mapped.
- [x] 2-card minimalist layout specified with progressive disclosure.
- [x] All clutter (sidebars, extraneous charts, settings) eliminated.
- [x] Collapsible drawer pattern defined for DICOM audit tags.
- [x] Download action specified for decrypted scan.
- [ ] Next Step: User review & approval of `FRONTEND_SPEC.md` prior to code generation.

