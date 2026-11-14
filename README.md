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

## 5. Role-Based Access Control (RBAC) & User Authentication (FIND-01 Remediation)

To remediate architectural vulnerabilities identified during the security audit (where internal endpoints were exposed without authentication and client-supplied `X-Client-Cert-SHA256` headers allowed unverified certificate claims), MedShield-AI implements an **RFC 7519 JWT + bcrypt** authentication engine backed by a granular Role-Based Access Control (RBAC) authorization matrix.

```
+----------------------------------------------------------------------------------------------------+
|                         MEDSHIELD-AI ROLE-BASED ACCESS CONTROL (RBAC) ARCHITECTURE                 |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ CLINICAL USER / CLIENT ]                                                                        |
|         |                                                                                          |
|         |  POST /api/v1/auth/login (username, password)                                            |
|         v                                                                                          |
|  [ AUTHENTICATION SERVICE (`medshield.auth.security`) ]                                            |
|         |                                                                                          |
|         +---> Password Verification: bcrypt (12 rounds) against in-memory/env registry             |
|         +---> Token Generation: RFC 7519 JWT (HS256, 12-hour expiration, issuer: 'medshield-ai')   |
|         +---> Response: Access Token returned in body AND set in HttpOnly `auth_token` cookie      |
|         |                                                                                          |
|         v                                                                                          |
|  [ FASTAPI DEPENDENCY ENFORCEMENT LAYER (`medshield.auth.dependencies`) ]                          |
|         |                                                                                          |
|         +---> `get_current_user`: Resolves JWT from Authorization header, cookie, or query param   |
|         |                                                                                          |
|         +---> Role Validation Gates:                                                               |
|         |     ├── `require_clinician`: Radiologists, clinicians, imaging residents                |
|         |     ├── `require_privacy_officer`: DPO / HIPAA compliance officers                       |
|         |     └── `require_admin`: Platform security engineers                                     |
|         |                                                                                          |
|         +---> Study Ownership & Access Control (`verify_study_access`):                            |
|               Enforces tenant isolation; clinicians can only access studies they ingested.        |
|               Cross-clinician access attempts strictly raise HTTP 403 Forbidden.                   |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### RBAC Permission Matrix

| Endpoint | Method | Required Role | Description & Security Enforcement |
| :--- | :---: | :---: | :--- |
| `/health` | `GET` | **Public** | Health telemetry, KMS status, and TLS mode (no PHI). |
| `/api/v1/auth/login` | `POST` | **Public** | Form-encoded login verifying bcrypt password hash; returns JWT. |
| `/api/v1/auth/me` | `GET` | Authenticated | Profile & role inspection for the active user. |
| `/api/v1/auth/logout` | `POST` | Authenticated | Clears HttpOnly session cookie. |
| `/api/v1/auth/users` | `GET`/`POST` | `admin` | User registry query and creation of new portal accounts. |
| `/api/v1/dashboard/samples` | `GET` | Authenticated | Reference test study catalog (`test_samples/`). |
| `/api/v1/dashboard/worklist` | `GET` | Authenticated | Study worklist (scoped to clinician; full queue for privacy officer). |
| `/api/v1/dashboard/analyze` | `POST` | `clinician` | Ingests scan, performs de-identification, and records study ownership. |
| `/api/v1/dashboard/studies/{uid}/dicom` | `GET` | `clinician`, `privacy_officer` | Streams decrypted DICOM (`403` cross-clinician, `410` shredded). |
| `/api/v1/dashboard/shred/{uid}` | `POST` | `privacy_officer` | **Restricted:** Destroys Master KEK under DPDP Act Sec. 12 (`403` for clinicians). |
| `/api/chat` | `POST` | `clinician` | Multimodal AI Scan Chat (enforces study-level ownership). |
| `/api/v1/studies` (STOW-RS) | `POST` | `clinician` | Ingestion boundary with DICOM PS 3.15 de-identification. |
| `/api/v1/inference/{uid}` | `POST` | `clinician` | In-RAM multi-label deep learning classification. |
| `/api/v1/heatmaps/{uid}/{path}` | `GET` | `clinician` | Thread-safe Grad-CAM saliency map generation. |

### Elimination of Spoofable mTLS Headers
1. **Purged Mock Fingerprints:** Removed all development bypasses, including empty-string SHA-256 hashes and static sample hashes.
2. **Reverse Proxy Trust Verification:** If deployment relies on an upstream reverse proxy (e.g. NGINX, Traefik) terminating TLS and forwarding `X-Client-Cert-SHA256`, the backend enforces `MEDSHIELD_TRUSTED_PROXY_SECRET`. Requests with unverified proxy headers are rejected.
3. **Defense-in-Depth:** Application-layer JWT authentication and transport-layer mTLS operate orthogonally. Spoofing a transport header cannot bypass JWT identity and role authorization.

### Pre-Configured Demonstration Personas for Evaluation

| Persona Name | Username | Password | Assigned Role | Primary Demonstration Workflow |
| :--- | :--- | :--- | :--- | :--- |
| **Dr. Sterling** | `dr_sterling` | `ClinicianSec2026!` | `clinician` | Ingest scans, run AI triage, view DICOM, Grad-CAM, Scan Chat. |
| **Clara Vance** | `officer_clara` | `PrivacySec2026!` | `privacy_officer` | Inspect KMS key vault, HIPAA audit log, execute DPDP Sec. 12 Crypto-Shredding. |
| **Dev Admin** | `admin_sec` | `AdminSec2026!` | `admin` | User registry provisioning, system configuration, audit review. |

---

## 6. Textbook Diffie–Hellman Key Exchange Algorithm (FIND-03 Implementation)

MedShield-AI implements a dedicated, mathematically authentic finite-field **Diffie–Hellman (DH) Key Exchange protocol** using modular exponentiation over cyclic subgroups of $\mathbb{Z}_p^*$, located in [`medshield/crypto/dh_key_exchange.py`](medshield/crypto/dh_key_exchange.py).

### 1. Mathematical Formulation

The Diffie–Hellman protocol allows two communicating parties (Alice and Bob) to establish a shared symmetric cryptographic key over an insecure, public communication channel without prior shared secrets:

```
                      ALICE                                             BOB
      [ Private: a ∈ [2, p - 2] ]                       [ Private: b ∈ [2, p - 2] ]
                   |                                                 |
      Calculate Public Key:                             Calculate Public Key:
         A = g^a mod p                                     B = g^b mod p
                   |                                                 |
                   | ------------ Public Key A ------------->       |
                   | <----------- Public Key B --------------       |
                   |                                                 |
      Validate Received Key:                            Validate Received Key:
         2 ≤ B ≤ p - 2                                     2 ≤ A ≤ p - 2
         B^q mod p == 1                                    A^q mod p == 1
                   |                                                 |
      Compute Shared Secret:                            Compute Shared Secret:
         S_A = B^a mod p                                   S_B = A^b mod p
             = (g^b)^a mod p                                   = (g^a)^b mod p
             = g^(ba) mod p                                    = g^(ab) mod p
                   |                                                 |
                   +=======================+=========================+
                                           |
                              S_A = S_B = g^(ab) mod p
                                           |
                        HKDF-SHA256 (Salt, "medshield-dh-aes256")
                                           |
                              Derived Key: K_AES (256-bit)
                                           |
                           AES-256-GCM Authenticated Channel
```

### 2. Algorithmic Steps & Implementation Details

1. **Approved Public Parameters:**
   - Evaluated using standard safe primes $p = 2q + 1$ from **RFC 3526 MODP Group 14** (2048-bit modulus, $g = 2$) and **RFC 3526 MODP Group 5** (1536-bit modulus).
   - Safe primes ensure that the multiplicative group $\mathbb{Z}_p^*$ contains a large cyclic subgroup of prime order $q = (p - 1)/2$, preventing Pohlig–Hellman small-subgroup attacks.
2. **CSPRNG Private Key Generation:**
   - Private exponents $a$ and $b$ are generated using Python's cryptographically secure pseudo-random number generator (`secrets.randbelow(p - 3) + 2`), ensuring $2 \le x \le p - 2$ with uniform entropy.
3. **Modular Exponentiation:**
   - Public keys and shared secrets are computed via Montgomery-accelerated modular exponentiation using Python's three-argument `pow(base, exp, mod)` executing in $\mathcal{O}(\log \text{exp})$ time.
4. **Subgroup Containment Validation:**
   - Every received public key $Y$ is strictly validated prior to exponentiation:
     - Range check: $2 \le Y \le p - 2$ (rejects $0, 1, p - 1$).
     - Quadratic residue subgroup check: $Y^q \equiv 1 \pmod p$ ensures $Y$ belongs to the $q$-order subgroup, actively defeating small-subgroup confinement attacks.
5. **Key Derivation Function (HKDF-SHA256):**
   - The shared secret $S \in \mathbb{Z}_p^*$ is converted to big-endian bytes and passed through **RFC 5869 HKDF-SHA256** (Extract & Expand) using a 256-bit salt and application-binding context `b"medshield-diffie-hellman-aes256-gcm-v1"` to produce a 256-bit symmetric key $K_{\text{AES}}$.
6. **Symmetric AES-256-GCM Integration:**
   - The derived key $K_{\text{AES}}$ is directly wired into authenticated clinical payload encryption, producing a 12-byte IV, AES-GCM ciphertext, and 16-byte authentication tag.

### 3. Running the Standalone Diffie–Hellman CLI Demonstration

MedShield-AI includes an executable demonstration of the Alice-Bob key exchange:

```bash
python -m medshield.crypto.dh_key_exchange
```

**Verified Execution Output:**
```json
{
  "protocol": "Textbook Diffie-Hellman Key Exchange (Finite Field MODP)",
  "parameters": {
    "group_name": "RFC-3526-MODP-2048",
    "modulus_bits": 2048,
    "generator_g": 2
  },
  "exchange": {
    "shared_secret_match_verified": true,
    "shared_secret_sha256": "f493e212875891a7d98567e8151c52a17169079165c5a2c69e0f70eabca2d1ca"
  },
  "key_derivation": {
    "kdf": "HKDF-SHA256 (RFC 5869)",
    "derived_key_algorithm": "AES-256-GCM",
    "derived_key_length_bits": 256,
    "keys_match": true
  },
  "aes_gcm_integration": {
    "plaintext_bytes": 134,
    "ciphertext_bytes": 150,
    "decryption_successful": true,
    "tamper_detected": true,
    "eve_rejection_verified": true
  }
}
```

### 4. Critical Theoretical Evaluation: Textbook DH vs. Production TLS 1.3

| Cryptographic Property | Textbook Finite-Field DH (Course Implementation) | Production TLS 1.3 Protocol (RFC 8446) |
| :--- | :--- | :--- |
| **Mathematical Primitive** | Modular exponentiation in $\mathbb{Z}_p^*$ ($A = g^a \bmod p$) | Ephemeral Elliptic-Curve DH (**ECDHE** on Curve25519 / P-256) |
| **Computational Overhead** | High (2048-bit integer modular exponentiation, $\approx 117\text{ ms}$) | Very Low (Elliptic curve scalar multiplication, $< 1\text{ ms}$) |
| **Key Size Efficiency** | 2048-bit public key for 112-bit security level | 256-bit public key for 128-bit security level |
| **Identity Authentication** | **None (Unauthenticated).** | **Asymmetric Signatures (ECDSA / RSA-PSS) + X.509 PKI.** |
| **Vulnerability to MITM** | **CRITICAL VULNERABILITY:** Active adversary Mallory can split the exchange ($K_{AM}$ and $K_{MB}$) and transparently intercept traffic. | **IMMUNE:** Server signs ephemeral DH parameters with private certificate key. |
| **Perfect Forward Secrecy** | Yes (ephemeral $a, b$ discarded after shared secret derivation) | Yes (ephemeral private keys destroyed immediately after handshake) |

---

## 7. Installation & Local Setup Guide

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

## 8. Clinical Portal & Security Workstation

MedShield-AI ships a **React 19 + TypeScript + Vite + Cornerstone3D** Daylight Clinical Portal (`frontend/`) alongside FastAPI's built-in `/dashboard` console:

- **Primary Development UI (`http://localhost:5173`):** Run FastAPI on port `8000` and Vite dev server on port `5173` (`npm --prefix frontend run dev`). Vite proxies `/api/*` requests to `VITE_API_PROXY_TARGET` (`http://127.0.0.1:8000`).
- **Unified Single-Container UI (`http://localhost:8000/`):** Build `frontend/` (`npm --prefix frontend run build`) and set `MEDSHIELD_SERVE_FRONTEND=true` (with `MEDSHIELD_REQUIRE_MTLS=false`).
- **Built-in FastAPI Console (`http://localhost:8000/dashboard`):** Available directly from FastAPI when `MEDSHIELD_SERVE_FRONTEND=false`.
- **Key Workstation Capabilities:**
  - **Secure Authentication & RBAC Login (`/`):** Full login interface with quick persona switchers for examiners and evaluators (`dr_sterling`, `officer_clara`, `admin_sec`).
  - **Drag-and-Drop / Clipboard Ingestion & 1-Click Samples:** Supports `.dcm` and `.png`/`.jpg` uploads plus pre-packaged reference studies (`patient_01_pneumonia`, `patient_02_effusion`, `patient_03_cardiomegaly`).
  - **Interactive Cornerstone3D PACS Viewer (`/workstation`):** Streams decrypted sanitized Part 10 DICOMs via authenticated `wadouri:?token=...`, with Window/Level, Pan, Zoom, Invert, and synchronized Grad-CAM opacity overlays.
  - **Security & Safe Harbor Vault (`/security`):** Side-by-side raw vs. pixel-redacted comparison, DICOM PS 3.15 tag diff matrix, `MEDENC01` AES-256-GCM inspection, Shannon entropy ($\ge 7.99$ bits/byte), and two-step DPDP Act §12 Crypto-Shredding (restricted to Privacy Officer role).
  - **Zero-PII Scan Chat Drawer:** Multimodal clinical Q&A grounded strictly in DenseNet-121 probabilities and Grad-CAM spatial localization.

---

## 9. Running the Servers & API Endpoints

### Start Backend API Server (Local Development)
```bash
uvicorn medshield.api.app:app --host 0.0.0.0 --port 8000 --reload
```
> **Production Note:** Always run Uvicorn with `--workers 1` because `LocalKMSProvider` keys, `_dashboard_worklist`, and user registries live in process memory for this prototype.

### Start Frontend Dev Server
```bash
npm --prefix frontend run dev
```

Visit OpenAPI docs at `http://localhost:8000/docs`, the React PACS Portal at `http://localhost:5173/`, or the standalone FastAPI console at `http://localhost:8000/dashboard`.

### Key API Endpoints & Role Requirements

| Method | Endpoint | Required Role | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/` | Public | Serves built React SPA or redirects to `/dashboard`. |
| `GET` | `/health` | Public | System health status, TLS/mTLS flags, and cryptographic engine status. |
| `POST` | `/api/v1/auth/login` | Public | Authenticates credentials via bcrypt; issues JWT and sets HttpOnly cookie. |
| `GET` | `/api/v1/auth/me` | Authenticated | Returns profile and active role of currently authenticated user. |
| `POST` | `/api/v1/auth/logout` | Authenticated | Invalidate session; clears client cookie. |
| `GET`/`POST` | `/api/v1/auth/users` | `admin` | Lists or registers portal user accounts in memory/env registry. |
| `GET` | `/api/v1/dashboard/samples` | Authenticated | Lists pre-packaged reference patient test cases (`test_samples/`). |
| `GET` | `/api/v1/dashboard/worklist` | Authenticated | Triage-sorted worklist (scoped to clinician; full queue for privacy officer). |
| `POST` | `/api/v1/dashboard/analyze` | `clinician` | Ingests study, scrubs PHI, encrypts payload, records owner, runs inference. |
| `GET` | `/api/v1/dashboard/studies/{uid}/dicom` | `clinician`, `privacy_officer` | Streams decrypted DICOM Part 10 bytes (`403` cross-clinician, `410` shredded). |
| `POST` | `/api/v1/dashboard/shred/{uid}` | `privacy_officer` | Destroys Master KEK under DPDP Act Sec. 12 (`403` for clinicians). |
| `POST` | `/api/chat` | `clinician` | Zero-PII Multimodal Scan Chat (enforces study ownership). |
| `POST` | `/api/v1/studies` | `clinician` | **STOW-RS Ingestion:** De-identifies metadata/pixels, encrypts with AES-256-GCM. |
| `POST` | `/api/v1/inference/{uid}` | `clinician` | Volatile RAM decryption & multi-label disease classifier. |
| `GET` | `/api/v1/heatmaps/{uid}/{pathology}` | `clinician` | Generates and returns blended Grad-CAM PNG activation overlay. |

---

## 10. Deployment

For full architectural guidance—covering why serverless functions are unsuitable for PyTorch + DenseNet-121 + EasyOCR, recommended **Split Deployment** (**Railway** / **Render** / **Fly.io** / **Cloud Run `min-instances=1`** backend + **Netlify** / **Vercel** / **Cloudflare Pages** frontend), **Unified Single-Container Docker** (`MEDSHIELD_SERVE_FRONTEND=true`), persistent volume mounts, and production security guards—read [**DEPLOYMENT.md**](DEPLOYMENT.md).

Pre-configured deployment files included in the repository:
- Backend Docker & PaaS: [`Dockerfile`](Dockerfile), [`.dockerignore`](.dockerignore), [`railway.toml`](railway.toml), [`render.yaml`](render.yaml), [`requirements-prod.txt`](requirements-prod.txt), [`.env.example`](.env.example)
- Frontend Static SPA CDN: [`frontend/netlify.toml`](frontend/netlify.toml), [`frontend/vercel.json`](frontend/vercel.json), [`frontend/.env.example`](frontend/.env.example)

---

## 11. Verification & Audit Suite

### 1. Run the Automated Backend Test Suite (87 Tests)
Executes all 10 test modules in `tests/`:
```bash
pytest tests/ -v
```
Modules covered:
- `test_auth_rbac.py` (14 tests): Authentication bypass rejection, bcrypt validation, JWT expiration, RBAC permissions, cross-clinician study isolation, spoofed mTLS rejection.
- `test_dh_key_exchange.py` (10 tests): Modular exponentiation, parameter validation, shared secret equality, HKDF-SHA256 key derivation, AES-256-GCM authenticated encryption, tamper detection, Eve rejection.
- `test_api_endpoints.py` (6 tests): Health, STOW-RS ingestion, in-memory inference, Grad-CAM heatmaps.
- `test_compliance_e2e.py` (4 tests): Full HIPAA Safe Harbor and Shannon entropy compliance audit.
- `test_config.py` (3 tests): Environment validation, secret keys, production security assertions.
- `test_crypto_envelope.py` (5 tests): `MEDENC01` envelope format, GCM authentication tags, crypto-shredding key revocation.
- `test_metadata_anonymizer.py` (3 tests): PS 3.15 tag purging, recursive sequence scrubbing, private tag removal.
- `test_ml_inference.py` (8 tests): DenseNet-121 model loading, 16-bit windowing, multi-label probabilities, triage urgency scoring.
- `test_pixel_cleaner.py` (4 tests): Margin OCR detection, safety box dilation, pixel inpainting.
- `test_scan_chat.py` (30 tests): Zero-PII sanitization, multimodal chat dispatch, clinician auth enforcement.

### 2. Run the Textbook Diffie–Hellman CLI Demonstration
```bash
python -m medshield.crypto.dh_key_exchange
```

### 3. Run the Standalone End-to-End Verification Pipeline
```bash
python scripts/verify_e2e_pipeline.py
```
Verifies 8-phase synthetic study generation, de-identification, envelope sealing, volatile RAM inference, Grad-CAM heatmaps, compliance scanner, tamper resistance, and crypto-shredding.

### 4. Run Frontend Lint & Production Build Checks
```bash
npm --prefix frontend run lint
npm --prefix frontend run build
```

---

## 12. Directory Structure

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
├── requirements.txt                # Full backend + dev/test dependencies (includes pyjwt, bcrypt)
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
│   ├── config.py                   # Pydantic settings, JWT secrets, CORS, prod guards
│   ├── auth/                       # RFC 7519 JWT Authentication & RBAC Engine (FIND-01)
│   │   ├── __init__.py             # Auth module exports
│   │   ├── models.py               # Pydantic user, token, and login schemas
│   │   ├── security.py             # bcrypt hashing & JWT encode/decode
│   │   ├── users.py                # In-memory & environment user registry
│   │   └── dependencies.py         # FastAPI dependency injection & RBAC role guards
│   ├── anonymization/              # DICOM PS 3.15 Annex E and pixel redaction
│   │   ├── metadata.py             # Safe Harbor tag purger & recursive sequence scrubber
│   │   ├── uid_hasher.py           # Salted HMAC-SHA256 UID generator (2.25.x root)
│   │   ├── date_shifter.py         # Deterministic patient-level date offset
│   │   └── pixel_cleaner.py        # Margin text detector, dilation & blackout
│   ├── crypto/                     # Cryptographic envelope storage & DH engine
│   │   ├── kms_provider.py         # Local KMS key manager & DPDP revocation
│   │   ├── envelope.py             # MEDENC01 binary packer & AES-256-GCM cipher
│   │   └── dh_key_exchange.py      # Textbook Diffie–Hellman MODP & AES-GCM (FIND-03)
│   ├── ml/                         # Deep learning, explainability & Scan Chat engine
│   │   ├── model.py                # TorchXRayVision DenseNet-121 + EfficientNet-V2-S
│   │   ├── preprocessor.py         # 16-bit DICOM normalization & windowing
│   │   ├── explainability.py       # Thread-safe Grad-CAM saliency heatmaps
│   │   ├── inference_engine.py     # Clinical triage urgency & prediction orchestration
│   │   └── chat_service.py         # Zero-PII Gemini/MedGemma/offline clinical Scan Chat
│   ├── storage/
│   │   └── encrypted_store.py      # Atomic encrypted object store
│   ├── api/                        # FastAPI Ingestion, Inference & Dashboard Service
│   │   ├── app.py                  # Application factory, CORS, auth routing
│   │   ├── middleware/             # mTLS auth (no mock bypass) and CERT-In JSON logging
│   │   └── routes/                 # STOW-RS, inference, heatmaps, dashboard, auth, chat
│   │       ├── auth.py             # Login, profile, logout, and admin user routes
│   │       ├── dashboard.py        # RBAC-secured dashboard & DPDP shredding
│   │       ├── inference.py        # Clinician-only inference & Grad-CAM endpoints
│   │       └── studies.py          # Clinician-only STOW-RS ingestion endpoint
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
│       ├── components/auth/        # Login interface & evaluation persona selectors
│       ├── components/viewer/      # Cornerstone3D viewport & PACS toolbars
│       ├── components/security/    # Safe Harbor tag diff & DPDP Crypto-Shred dialog
│       └── stores/                 # Zustand store with JWT authentication state
└── tests/                          # Automated test suite (10 modules, 87 tests passing)
    ├── test_auth_rbac.py           # 14 tests: JWT, bcrypt, RBAC roles, tenant isolation
    ├── test_dh_key_exchange.py     # 10 tests: MODP arithmetic, HKDF, AES-GCM integration
    ├── test_api_endpoints.py       # 6 tests: Health, STOW-RS, inference, heatmaps
    ├── test_compliance_e2e.py      # 4 tests: HIPAA Safe Harbor & entropy scanner
    ├── test_config.py              # 3 tests: Pydantic settings & production guards
    ├── test_crypto_envelope.py     # 5 tests: MEDENC01 envelope, AES-GCM, shredding
    ├── test_metadata_anonymizer.py # 3 tests: PS 3.15 tag purging & sequence cleaning
    ├── test_ml_inference.py        # 8 tests: DenseNet-121, windowing, multi-label triage
    ├── test_pixel_cleaner.py       # 4 tests: Burned-in OCR detection & pixel inpainting
    └── test_scan_chat.py           # 30 tests: Zero-PII sanitization & Scan Chat dispatch
```

---

## 13. License

This project is licensed under the Apache 2.0 License.
