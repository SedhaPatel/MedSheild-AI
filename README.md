# MedShield-AI

**Secure, HIPAA & India DPDP-Compliant AI Medical Image Disease Detection System**

> **Production & Cloud Hosting:** See [**DEPLOYMENT.md**](DEPLOYMENT.md) for the complete architecture guide (recommended split Docker PaaS + CDN SPA deployment, unified single-container Docker mode, memory/storage requirements, and environment reference).

---

## 1. Executive Overview & Problem Statement

Modern clinical environments generate massive volumes of medical imaging (with chest radiographs accounting for $>40\%$ of all hospital imaging volume). While deep learning algorithms demonstrate radiologist-level diagnostic performance for thoracic pathologies, deploying AI into hospital workflows introduces critical data privacy and cybersecurity vulnerabilities:

- **Metadata PHI Leakage:** DICOM files contain dozens of patient identifiers across primary tags and nested sequence elements (`PatientName`, `PatientID`, `InstitutionName`, `ReferringPhysicianName`).
- **Burned-In Pixel PHI:** Ultrasound borders and secondary capture radiographs frequently contain patient names and MRNs rasterized directly into the pixel array, bypassing standard header scrubbers.
- **Storage-at-Rest Vulnerabilities:** Plaintext DICOM storage risks catastrophic breaches violating **HIPAA Security Rule §164.312(a)(2)(iv)** and **India DPDP Act 2023 Section 8(5)**.
- **Regulatory Erasure Non-Compliance:** Regulations such as the India DPDP Act (Section 12) mandate the right to erasure, which is virtually impossible to enforce when patient studies are immutably distributed across backups without cryptographic isolation.

**MedShield-AI** solves this by establishing a zero-trust, privacy-by-design clinical AI pipeline. It ingests raw DICOM studies over mutual TLS (mTLS), sanitizes PHI across both metadata and pixel domains, seals data using hardware-backed **AES-256-GCM Envelope Encryption**, executes deep learning multi-label disease triage in volatile RAM with zero plaintext spooling to disk, and provides explainable **Grad-CAM** visual saliency maps for radiologists.

---

## 2. Security & Regulatory Compliance Architecture

MedShield-AI maps directly to statutory healthcare data protection standards:

```
+---------------------------------------------------------------------------------------------------+
|                                  MEDSHIELD-AI SYSTEM ARCHITECTURE                                 |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ ON-PREMISE HOSPITAL EDGE ROUTER / PACS ]                                                       |
|        |                                                                                          |
|        |  mTLS (TLS 1.3, TLS_AES_256_GCM_SHA384, Client Cert Pinning, 0-RTT Disabled)            |
|        v                                                                                          |
|  [ INGESTION & DE-IDENTIFICATION BOUNDARY (FastAPI STOW-RS Endpoint) ]                            |
|        |                                                                                          |
|        +---> Metadata De-Identification Engine (DICOM PS 3.15 Annex E Basic Profile)             |
|        |     - Safe Harbor: 18 HIPAA Identifiers Scrubbed (Action X/Z)                            |
|        |     - UID Pseudonymization: Salted HMAC-SHA256 with '2.25.' root (Action U)              |
|        |     - Date Shifting: Salted patient-level day offset preserving longitudinal RECIST      |
|        |     - Sequence Cleaning & Vendor Private Tag Purging (Odd Group Numbers)                 |
|        |                                                                                          |
|        +---> Dual-Stage Pixel De-Identification Engine                                            |
|              - Margin Bounding Box Text Detector (Ultrasound/Secondary Capture)                   |
|              - Safety Dilatation: >= 15% bounding-box padding covering descenders/ascenders       |
|              - Pixel Inpainting: High-contrast text zeroed out; BurnedInAnnotation set to 'NO'    |
|        |                                                                                          |
|        v                                                                                          |
|  [ ZERO-TRUST CRYPTOGRAPHIC STORAGE ENGINE (Envelope Encryption) ]                                |
|        |                                                                                          |
|        +---> KMS / HSM (FIPS 140-3 Level 3 Interface)                                             |
|        |     - Master KEK (Key Encryption Key): 256-bit AES-GCM retained in HSM                   |
|        |     - Per-Study Ephemeral DEK: 256-bit generated via CSPRNG per study                   |
|        |     - Encrypted DEK: Wrapped by Master KEK with 96-bit IV + Auth Tag                     |
|        |                                                                                          |
|        +---> Atomic Storage Layer (`.enc` files)                                                  |
|              - Container Format: 'MEDENC01' Binary Envelope                                       |
|              - Payload: AES-256-GCM Ciphertext (Shannon Entropy >= 7.99 bits/byte)                |
|              - Crypto-Shredding: Instant DPDP Sec 12 Erasure via KEK/DEK Key Revocation           |
|        |                                                                                          |
|        v                                                                                          |
|  [ VOLATILE DEEP LEARNING INFERENCE SERVICE (Zero-Disk Plaintext Spooling) ]                      |
|        |                                                                                          |
|        +---> In-Memory Decryption: Decrypted strictly within RAM buffer                           |
|        +---> 16-Bit Normalization: Dynamic range windowing & MONOCHROME1 inversion                |
|        +---> Deep Classifier: EfficientNet-V2-S / ConvNeXt-V2-Base                                |
|        +---> Multi-Label Pathologies: Pneumonia, Cardiomegaly, Effusion, Pneumothorax, Atelectasis|
|        +---> Uncertainty & Triage: Calibrated Epistemic Uncertainty + STAT Urgency Scoring        |
|        +---> Explainability: Thread-safe Grad-CAM saliency heatmaps overlaid on native DICOM     |
|        |                                                                                          |
|        v                                                                                          |
|  [ IMMUTABLE CERT-IN & HIPAA §164.312(b) AUDIT TRAIL ]                                            |
|        - NTP-synchronized Structured JSON Logging (ISO 8601 UTC)                                  |
|        - Captures: SHA-256 cert fingerprint, anonymous UID, latency, model checkpoint hash        |
|        - Guaranteed zero PHI leakage in log files                                                 |
+---------------------------------------------------------------------------------------------------+
```

### Regulatory Compliance Mapping

| Regulatory Authority & Provision | Statutory Requirement | MedShield-AI Implementation |
| :--- | :--- | :--- |
| **US HIPAA Privacy Rule §164.514(b)** | Safe Harbor De-identification (18 identifiers) | Automatic stripping of all 18 identifiers, recursive sequence sanitization, private vendor tag removal, and pixel text blackout. |
| **US HIPAA Security Rule §164.312(a)(2)(iv)** | Encryption and decryption of ePHI at rest | FIPS 140-3 compliant envelope encryption using AES-256-GCM (`MEDENC01` binary envelope). |
| **US HIPAA Security Rule §164.312(e)(1)** | Transmission security for ePHI in transit | TLS 1.3 enforcing `TLS_AES_256_GCM_SHA384`, mandatory mTLS client cert validation, 0-RTT disabled. |
| **India DPDP Act 2023 Section 8(5)** | Implementation of reasonable security safeguards | Zero-trust enclave processing, segregated pseudonymization database, and memory-only plaintext decryption. |
| **India DPDP Act 2023 Section 12** | Right to Correction and Erasure (Crypto-Shredding) | Instant cryptographic erasure by revoking study DEK or Master KEK, rendering data mathematically irrecoverable. |
| **India CERT-In Directions 2022** | 6-Hour incident reporting & 180-day audit trails | Structured JSON audit logger emitting NTP-synchronized logs for all ingestion and decryption events. |

---

## 3. Cryptographic Storage Specification (`MEDENC01`)

MedShield-AI serializes encrypted studies into an authenticated binary envelope:

```
+---------------+----------------+----------------+----------------+--------------------+
| Magic Header  | KEK ID Length  |   KEK Key ID   | DEK Enc Length |  Encrypted Study   |
|   (8 bytes)   |    (2 bytes)   |   (Variable)   |   (4 bytes)    |    DEK Payload     |
|   'MEDENC01'  |   Big-Endian   |   UTF-8 String |   Big-Endian   |  [IV + DEK + Tag]  |
+---------------+----------------+----------------+----------------+--------------------+
| Payload IV    |   Ciphertext   | GCM Auth Tag   |
|  (12 bytes)   |   (Variable)   |   (16 bytes)   |
+---------------+----------------+----------------+
```

- **Master Key (KEK):** Stored securely within HSM/KMS.
- **Data Key (DEK):** Ephemeral 256-bit symmetric key generated via CSPRNG per study, wrapped by KEK with AES-256-GCM.
- **Payload Ciphertext:** DICOM dataset encrypted with study DEK, achieving Shannon entropy $\ge 7.99$ bits/byte.
- **Tamper Resistance:** Any single-bit modification in the ciphertext or tag raises an uncatchable `cryptography.exceptions.InvalidTag` exception, rejecting compromised scans.
- **Crypto-Shredding:** Revoking a KEK or deleting the wrapped DEK fulfills DPDP Section 12 erasure in $<1\text{ ms}$ without expensive physical drive wipes.

---

## 4. Deep Learning Diagnostic Engine, Explainability & Scan Chat

- **Primary & Fallback Backbones:** **TorchXRayVision DenseNet-121** (`densenet121-res224-all`, cached in `weights/`), with **EfficientNet-V2-S** (`ThoracicClassifier`) fallback.
- **Target Pathologies:**
  1. *Pneumonia* (consolidation / inflammatory infiltrates)
  2. *Cardiomegaly* (cardiothoracic ratio $> 0.50$)
  3. *Pleural Effusion* (costophrenic angle blunting)
  4. *Pneumothorax* (visceral pleural line visualization — *STAT Critical*)
  5. *Atelectasis* (volume loss / linear opacity)
- **Triage Urgency Grading:**
  - `STAT_CRITICAL`: Pneumothorax or Pneumonia detected with high confidence ($p \ge 0.70$). Flagged for immediate emergency radiologist notification.
  - `ELEVATED`: Any target pathology detected at $p \ge 0.50$.
  - `ROUTINE`: All pathology probabilities $< 0.50$.
- **Explainability (Grad-CAM):** Thread-safe Class Activation Mapping calculating gradients of the target class score with respect to the final convolutional layer, mapped to an RGB heatmap overlay blended ($\alpha=0.45$) with the normalized radiograph.
- **Zero-PII Clinical Scan Chat (`medshield/ml/chat_service.py`):** Re-verifies HIPAA Safe Harbor compliance (`BurnedInAnnotation == "NO"`), strips accidental PII from clinician prompts/history, extracts sanitized PNG pixel frames (`<= 768x768`), and dispatches to **Gemini 2.5 Flash**, **MedGemma** (`google/medgemma-1.5-4b-it` via Hugging Face Router), or the deterministic `grounded-local-fallback` synthesizer when API keys are unset.

---

## 5. Installation & Local Setup Guide

### Prerequisites
- Python 3.10+ (Docker targets Python 3.11; tested on Windows/Linux/macOS)
- Node.js 20+ / npm (for the React + Cornerstone3D frontend in `frontend/`)
- PyTorch 2.0+ (CPU or CUDA-enabled GPU)

### 1. Clone & Create Virtual Environment
```bash
git clone https://github.com/medshield-ai/medshield.git
cd medshield

python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate
```

### 2. Install Backend & Frontend Dependencies
```bash
# Backend + dev/test dependencies
pip install -r requirements.txt
pip install -e .

# React + Cornerstone3D frontend dependencies
npm --prefix frontend install
```

### 3. Environment Configuration
Copy the documented environment templates and fill in secrets locally (`.env` and `.env.*` are gitignored):

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

Key backend variables (see [`.env.example`](.env.example) for all options):

```ini
# Core & Storage
MEDSHIELD_ENVIRONMENT=development
MEDSHIELD_DEBUG=false
MEDSHIELD_STORAGE_PATH=./storage/encrypted_studies

# Cryptographic Salt (MUST be a unique >=32-char secret when MEDSHIELD_ENVIRONMENT=production)
MEDSHIELD_SECRET_PEPPER=replace-with-unique-random-secret-at-least-32-chars
MEDSHIELD_KMS_MASTER_KEY_ID=arn:medshield:kms:local:key/master-kek-v1

# Security, mTLS & CORS
MEDSHIELD_REQUIRE_MTLS=false
MEDSHIELD_TLS_MIN_VERSION=TLSv1.3
MEDSHIELD_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000

# Optional Unified SPA Hosting (serve built frontend/dist from FastAPI)
MEDSHIELD_SERVE_FRONTEND=false
MEDSHIELD_FRONTEND_DIST_DIR=./frontend/dist

# Zero-PII Scan Chat VLM Options ("gemini" | "medgemma"; blank keys use grounded-local-fallback)
MEDSHIELD_CHAT_PROVIDER=gemini
GEMINI_API_KEY=
MEDSHIELD_GEMINI_MODEL=gemini-2.5-flash
HF_API_TOKEN=
MEDSHIELD_MEDGEMMA_MODEL=google/medgemma-1.5-4b-it
MEDSHIELD_CHAT_TIMEOUT_SEC=25.0
```

Frontend Vite variables (see [`frontend/.env.example`](frontend/.env.example)):

```ini
# Leave empty for local Vite proxy & unified single-container deployments;
# set to public FastAPI origin (e.g. https://medshield-api.up.railway.app) for split CDN hosting
VITE_API_BASE_URL=
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

---

## 6. Clinical Portal & Security Workstation

MedShield-AI ships a **React 19 + TypeScript + Vite + Cornerstone3D** Daylight Clinical Portal (`frontend/`) alongside FastAPI's built-in `/dashboard` console:

- **Primary Development UI (`http://localhost:5173`):** Run FastAPI on port `8000` and Vite dev server on port `5173` (`npm --prefix frontend run dev`). Vite proxies `/api/*` requests to `VITE_API_PROXY_TARGET` (`http://127.0.0.1:8000`).
- **Unified Single-Container UI (`http://localhost:8000/`):** Build `frontend/` (`npm --prefix frontend run build`) and set `MEDSHIELD_SERVE_FRONTEND=true` (with `MEDSHIELD_REQUIRE_MTLS=false`).
- **Built-in FastAPI Console (`http://localhost:8000/dashboard`):** Available directly from FastAPI when `MEDSHIELD_SERVE_FRONTEND=false`.
- **Key Workstation Capabilities:**
  - **Drag-and-Drop / Clipboard Ingestion & 1-Click Samples:** Supports `.dcm` and `.png`/`.jpg` uploads plus pre-packaged reference studies (`patient_01_pneumonia`, `patient_02_effusion`, `patient_03_cardiomegaly`).
  - **Interactive Cornerstone3D PACS Viewer (`/workstation`):** Streams decrypted sanitized Part 10 DICOMs via `wadouri:`, with Window/Level, Pan, Zoom, Invert, and synchronized Grad-CAM opacity overlays.
  - **Security & Safe Harbor Vault (`/security`):** Side-by-side raw vs. pixel-redacted comparison, DICOM PS 3.15 tag diff matrix, `MEDENC01` AES-256-GCM inspection, Shannon entropy ($\ge 7.99$ bits/byte), and two-step DPDP Act §12 Crypto-Shredding.
  - **Zero-PII Scan Chat Drawer:** Multimodal clinical Q&A grounded strictly in DenseNet-121 probabilities and Grad-CAM spatial localization.

---

## 7. Running the Servers & API Endpoints

### Start Backend API Server (Local Development)
```bash
uvicorn medshield.api.app:app --host 0.0.0.0 --port 8000 --reload
```
> **Production Note:** Always run Uvicorn with `--workers 1` because `LocalKMSProvider` keys, `_dashboard_worklist`, and `_dashboard_session_cache` live in process memory.

### Start Frontend Dev Server
```bash
npm --prefix frontend run dev
```

Visit OpenAPI docs at `http://localhost:8000/docs`, the React PACS Portal at `http://localhost:5173/`, or the standalone FastAPI console at `http://localhost:8000/dashboard`.

### Key API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Redirects to `/dashboard`, or serves built React SPA `index.html` when `MEDSHIELD_SERVE_FRONTEND=true`. |
| `GET` | `/dashboard` | Built-in FastAPI Clinical Reading & Security Console HTML page. |
| `GET` | `/health` | System health status, TLS/mTLS flags, and cryptographic engine status. |
| `GET` | `/api/v1/dashboard/samples` | Lists available pre-packaged patient test cases (`test_samples/`). |
| `GET` | `/api/v1/dashboard/worklist` | Returns triage-sorted ingested worklist entries. |
| `POST` | `/api/v1/dashboard/analyze` | Unified diagnostic & de-identification analysis for uploads, samples, or stored `study_uid`. |
| `GET` | `/api/v1/dashboard/studies/{study_uid}/dicom` | Streams decrypted sanitized DICOM Part 10 bytes for Cornerstone3D `wadouri:` or download (`410` after shredding). |
| `POST` | `/api/v1/dashboard/shred/{study_uid}` | Executes DPDP Section 12 Crypto-Shredding via study Master KEK revocation. |
| `POST` | `/api/chat` | Zero-PII Multimodal Scan Chat endpoint (aliased at `/api/v1/dashboard/chat`). |
| `POST` | `/api/v1/studies` | **DICOMweb STOW-RS:** Ingests raw DICOM, runs PS 3.15 de-identification, redacts pixel PHI, encrypts via AES-256-GCM, and persists to storage (mTLS protected when `MEDSHIELD_REQUIRE_MTLS=true`). |
| `POST` | `/api/v1/inference/{study_uid}` | Decrypts study in volatile RAM, runs thoracic multi-label disease classifier, and outputs calibrated probabilities and triage urgency. |
| `GET` | `/api/v1/heatmaps/{study_uid}/{pathology}` | Generates and returns a blended Grad-CAM PNG activation overlay for visual pathology localization. |

---

## 8. Deployment

For full architectural guidance—covering why serverless functions are unsuitable for PyTorch + DenseNet-121 + EasyOCR, recommended **Split Deployment** (**Railway** / **Render** / **Fly.io** / **Cloud Run `min-instances=1`** backend + **Netlify** / **Vercel** / **Cloudflare Pages** frontend), **Unified Single-Container Docker** (`MEDSHIELD_SERVE_FRONTEND=true`), persistent volume mounts, and production security guards—read [**DEPLOYMENT.md**](DEPLOYMENT.md).

Pre-configured deployment files included in the repository:
- Backend Docker & PaaS: [`Dockerfile`](Dockerfile), [`.dockerignore`](.dockerignore), [`railway.toml`](railway.toml), [`render.yaml`](render.yaml), [`requirements-prod.txt`](requirements-prod.txt), [`.env.example`](.env.example)
- Frontend Static SPA CDN: [`frontend/netlify.toml`](frontend/netlify.toml), [`frontend/vercel.json`](frontend/vercel.json), [`frontend/.env.example`](frontend/.env.example)

---

## 9. Verification & Audit Suite

### Run the Automated Backend Test Suite
Executes all 8 test modules in `tests/` (metadata stripping, pixel cleaning, crypto envelope, ML inference, API endpoints, compliance E2E, config, and zero-PII Scan Chat):
```bash
python -m pytest tests/ -v
```

### Run the Standalone End-to-End Verification Pipeline
MedShield-AI includes a comprehensive, standalone 8-phase verification script:
```bash
python scripts/verify_e2e_pipeline.py
```

This verifies the complete workflow:
1. Synthesizes a raw DICOM study with detectable HIPAA Safe Harbor identifiers and burned-in text.
2. Ingests and sanitizes metadata and detects/inpaints burned-in text.
3. Inspects encrypted storage, confirming Shannon entropy $\ge 7.99$ bits/byte and 0 plaintext leaks.
4. Executes volatile RAM decryption and deep learning disease classification.
5. Generates and validates an explainable Grad-CAM visual heatmap image.
6. Audits the decrypted dataset with `ComplianceScanner`, confirming 0 Safe Harbor violations.
7. Validates cryptographic tamper resistance via AES-256-GCM authentication failure.
8. Validates instant crypto-shredding under DPDP Act Section 12 via Master KEK revocation.

### Run Frontend Lint & Production Build Checks
```bash
npm --prefix frontend run lint
npm --prefix frontend run build
```

---

## 10. Directory Structure

```
.
├── DEPLOYMENT.md                   # Split & unified deployment architecture guide
├── Dockerfile                      # Multi-stage Node 22 + Python 3.11-slim CPU-PyTorch build
├── .dockerignore                   # Excludes local weights/, storage/, tests/, node_modules/
├── .env.example                    # Backend environment configuration template
├── .gitignore                      # Ignores storage/, weights/, .env/.env.*, build caches
├── pyproject.toml                  # Package metadata, dependencies & pytest config
├── railway.toml                    # Railway Docker service + /health check config
├── render.yaml                     # Render Docker service + 5 GB persistent disk config
├── requirements.txt                # Full backend + dev/test dependencies
├── requirements-prod.txt           # Runtime-only production dependencies for Docker
├── skills-lock.json                # Installed skill provenance lockfile
├── docs/                           # Architecture, research, specs & implementation plans
│   ├── RESEARCH.md                 # Deep research brief on architectures & benchmarks
│   ├── SPEC.md                     # Complete system design specification
│   ├── PLAN.md                     # Implementation plan and task roadmap
│   ├── FRONTEND_SPEC.md            # Clinical portal & Zero-PII Scan Chat specification
│   └── superpowers/                # Detailed UI & Scan Chat implementation plans/specs
├── scripts/
│   └── verify_e2e_pipeline.py      # Standalone 8-phase end-to-end verification script
├── test_samples/                   # Pre-packaged chest X-ray samples (.dcm & .png)
├── medshield/
│   ├── config.py                   # Pydantic settings, CORS, SPA serving & prod guards
│   ├── anonymization/              # DICOM PS 3.15 Annex E and pixel redaction
│   │   ├── metadata.py             # Safe Harbor tag purger & recursive sequence scrubber
│   │   ├── uid_hasher.py           # Salted HMAC-SHA256 UID generator (2.25.x root)
│   │   ├── date_shifter.py         # Deterministic patient-level date offset
│   │   └── pixel_cleaner.py        # Margin text detector, dilation & blackout
│   ├── crypto/                     # Cryptographic envelope storage engine
│   │   ├── kms_provider.py         # Local KMS key manager & DPDP revocation
│   │   └── envelope.py             # MEDENC01 binary packer & AES-256-GCM cipher
│   ├── ml/                         # Deep learning, explainability & Scan Chat engine
│   │   ├── model.py                # TorchXRayVision DenseNet-121 + EfficientNet-V2-S
│   │   ├── preprocessor.py         # 16-bit DICOM normalization & windowing
│   │   ├── explainability.py       # Thread-safe Grad-CAM saliency heatmaps
│   │   ├── inference_engine.py     # Clinical triage urgency & prediction orchestration
│   │   └── chat_service.py         # Zero-PII Gemini/MedGemma/offline clinical Scan Chat
│   ├── storage/
│   │   └── encrypted_store.py      # Atomic encrypted object store
│   ├── api/                        # FastAPI Ingestion, Inference & Dashboard Service
│   │   ├── app.py                  # Application factory, CORS, optional SPA static host
│   │   ├── middleware/             # mTLS auth and CERT-In JSON audit logging
│   │   └── routes/                 # STOW-RS upload, inference, heatmaps, dashboard & chat
│   ├── utils/
│   │   ├── dicom_helpers.py        # Pixel array extraction & dataset serialization
│   │   └── logging.py              # Structured JSON audit logging formatter
│   └── verification/               # Compliance scanning & security audits
│       ├── compliance_scanner.py   # HIPAA Safe Harbor auditor
│       └── entropy_analyzer.py     # Shannon entropy calculator (>= 7.99 bits/byte)
├── frontend/                       # React 19 + Vite + TypeScript + Cornerstone3D SPA
│   ├── .env.example                # VITE_API_BASE_URL & VITE_API_PROXY_TARGET template
│   ├── netlify.toml                # Netlify SPA build, redirect & security headers
│   ├── vercel.json                 # Vercel SPA rewrite & asset caching headers
│   ├── package.json                # React 19, Cornerstone3D WASM, Tailwind v4, Radix UI
│   ├── vite.config.ts              # Vite build, WASM codecs & dev proxy config
│   └── src/                        # Pages, components, Zustand store, API client
└── tests/                          # Automated test suite across 8 modules
    ├── test_api_endpoints.py
    ├── test_compliance_e2e.py
    ├── test_config.py
    ├── test_crypto_envelope.py
    ├── test_metadata_anonymizer.py
    ├── test_ml_inference.py
    ├── test_pixel_cleaner.py
    └── test_scan_chat.py
```

---

## 11. License

This project is licensed under the Apache 2.0 License.
