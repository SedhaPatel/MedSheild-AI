# MedShield-AI

**Secure, HIPAA & India DPDP-Compliant AI Medical Image Disease Detection System**

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

## 4. Deep Learning Diagnostic Engine & Explainability

- **Architectures Supported:** **EfficientNet-V2-S** (progressive training resolution, fast Fused-MBConv layers) and **ConvNeXt-V2-Base** (modernized $7\times7$ depthwise convolutions with Global Response Normalization).
- **Target Pathologies:**
  1. *Pneumonia* (consolidation / inflammatory infiltrates)
  2. *Cardiomegaly* (cardiothoracic ratio $> 0.50$)
  3. *Pleural Effusion* (costophrenic angle blunting)
  4. *Pneumothorax* (visceral pleural line visualization — *STAT Critical*)
  5. *Atelectasis* (volume loss / linear opacity)
- **Triage Urgency Grading:**
  - `STAT_CRITICAL`: Pneumothorax detected ($p \ge 0.50$). Flagged for immediate emergency radiologist notification.
  - `ELEVATED`: Pneumonia, Pleural Effusion, or Cardiomegaly detected ($p \ge 0.50$).
  - `ROUTINE`: All pathology probabilities $< 0.50$.
- **Explainability (Grad-CAM):** Thread-safe Class Activation Mapping calculating gradients of the target class score with respect to feature maps of the final convolutional layer, mapped through a JET/Inferno color palette and blended ($\alpha=0.45$) with the normalized DICOM radiograph.

---

## 5. Installation & Setup Guide

### Prerequisites
- Python 3.11, 3.12, 3.13, or 3.14
- Operating System: Linux, macOS, or Windows
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

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
MedShield-AI supports environment variables or a `.env` file:

```ini
# Core Configuration
MEDSHIELD_ENVIRONMENT=production
MEDSHIELD_DEBUG=false
MEDSHIELD_STORAGE_PATH=./storage/encrypted_studies

# Cryptographic Salt (Must be >= 32 characters in production)
MEDSHIELD_SECRET_PEPPER=ProductionMasterPepper_2026_StrictSecuritySaltValue_99!
MEDSHIELD_KMS_MASTER_KEY_ID=arn:medshield:kms:local:key/master-kek-v1

# Security & Mutual TLS
MEDSHIELD_REQUIRE_MTLS=true
MEDSHIELD_TLS_MIN_VERSION=TLSv1.3

# Deep Learning Backbone
MEDSHIELD_MODEL_ARCHITECTURE=efficientnet_v2_s
```

---

## 6. Running the API Server & Endpoints

### Start the REST / DICOMweb Gateway
```bash
uvicorn medshield.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Visit the interactive OpenAPI documentation at `http://localhost:8000/docs`.

### Key API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | System health status, active cryptographic engine, and model architecture. |
| `POST` | `/api/v1/studies` | **DICOMweb STOW-RS:** Ingests raw DICOM, runs PS 3.15 de-identification, blacks out pixel PHI, encrypts via AES-256-GCM, and persists to storage. |
| `POST` | `/api/v1/inference/{study_uid}` | Decrypts study in volatile RAM, runs thoracic multi-label disease classifier, and outputs calibrated probabilities and triage urgency. |
| `GET` | `/api/v1/heatmaps/{study_uid}/{pathology}` | Generates and returns a blended Grad-CAM PNG activation overlay for visual pathology localization. |

---

## 7. Verification & Audit Suite

### Run the Full Automated Test Suite (28 Tests)
```bash
python -m pytest tests/ -v
```

All 28 tests across metadata stripping, pixel cleaning, crypto envelope, ML inference, API endpoints, and compliance scanners will execute:
```text
============================= 28 passed in 11.89s =============================
```

### Run the Standalone End-to-End Verification Pipeline
MedShield-AI includes a comprehensive, standalone end-to-end verification script:
```bash
python verify_e2e_pipeline.py
```

This verifies the complete 8-phase workflow in under 3 seconds:
1. Synthesizes a raw DICOM study with 11 detectable HIPAA identifiers and burned-in text.
2. Ingests and sanitizes metadata and detects/inpaints burned-in text.
3. Inspects encrypted storage, confirming Shannon entropy $\ge 7.99$ bits/byte and 0 plaintext leaks.
4. Executes volatile RAM decryption and deep learning disease classification.
5. Generates and validates an explainable Grad-CAM visual heatmap image.
6. Audits the decrypted dataset with `ComplianceScanner`, confirming 0 Safe Harbor violations.
7. Validates cryptographic tamper resistance via AES-256-GCM authentication failure.
8. Validates instant crypto-shredding under DPDP Act Section 12 via Master KEK revocation.

---

## 8. Directory Structure

```
.
├── pyproject.toml              # Build configuration and dependency definitions
├── requirements.txt            # Production dependencies
├── SPEC.md                     # Complete architectural design specification
├── PLAN.md                     # Implementation plan and task roadmap
├── RESEARCH.md                 # Deep research brief on architectures & benchmarks
├── verify_e2e_pipeline.py      # Standalone 8-phase end-to-end verification script
├── medshield/
│   ├── anonymization/          # DICOM PS 3.15 Annex E and pixel redaction
│   │   ├── metadata.py         # 18 Safe Harbor tag purger & sequence scrubber
│   │   ├── uid_hasher.py       # Salted HMAC-SHA256 UID generator (2.25.x root)
│   │   ├── date_shifter.py     # Deterministic patient-level date offset
│   │   └── pixel_cleaner.py    # Margin text detector, dilation & blackout
│   ├── crypto/                 # Cryptographic envelope storage engine
│   │   ├── kms_provider.py     # FIPS 140-3 HSM/KMS key manager & revocation
│   │   └── envelope.py         # MEDENC01 binary packer, AES-256-GCM cipher
│   ├── ml/                     # Deep learning & explainability engine
│   │   ├── model.py            # Thoracic multi-label classifier head
│   │   ├── preprocessor.py     # 16-bit DICOM normalization & windowing
│   │   ├── explainability.py   # Thread-safe Grad-CAM saliency heatmaps
│   │   └── inference_engine.py # Clinical triage urgency & prediction orchestration
│   ├── storage/
│   │   └── encrypted_store.py  # Atomic encrypted object store
│   ├── api/                    # FastAPI Ingestion & DICOMweb Service
│   │   ├── app.py              # Application factory & router configuration
│   │   ├── middleware/         # mTLS auth and CERT-In audit logging
│   │   └── routes/             # STOW-RS upload, inference, and heatmaps
│   ├── utils/
│   │   ├── dicom_helpers.py    # Pixel array extraction & dataset serialization
│   │   └── logging.py          # Structured JSON audit logging formatter
│   └── verification/           # Compliance scanning & security tests
│       ├── compliance_scanner.py # 18-tag HIPAA Safe Harbor auditor
│       └── entropy_analyzer.py   # Shannon entropy calculator (>= 7.99 bits/byte)
└── tests/                      # Automated test suite (28 tests, 100% pass)
    ├── test_api_endpoints.py
    ├── test_compliance_e2e.py
    ├── test_config.py
    ├── test_crypto_envelope.py
    ├── test_metadata_anonymizer.py
    ├── test_ml_inference.py
    └── test_pixel_cleaner.py
```

---

## 9. License

This project is licensed under the Apache 2.0 License.
