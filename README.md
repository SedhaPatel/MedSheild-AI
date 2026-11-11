# MedShield-AI

**Secure, HIPAA & India DPDP-Compliant AI Medical Image Disease Detection System**

---

## Overview

MedShield-AI is a production-grade healthcare AI platform built to ingest raw 2D thoracic radiographs (DICOM), sanitize Protected Health Information (PHI) across both metadata tags and pixel matrices, encrypt payloads using hardware-backed **AES-256-GCM Envelope Encryption**, and execute multi-label deep learning disease detection with **Grad-CAM visual explainability**.

The system is architected from the ground up to satisfy the statutory requirements of:
- **US HIPAA Privacy Rule §164.514(b)** (18 Safe Harbor identifiers de-identification)
- **US HIPAA Security Rule §164.312** (FIPS 140-3 storage encryption at rest & TLS 1.3 transit)
- **India Digital Personal Data Protection (DPDP) Act, 2023** (Sections 6, 8, and Section 12 Right to Erasure / Crypto-Shredding)
- **India CERT-In Cybersecurity Directives** (180-day structured audit trails & incident detection)

---

## Architecture Pipeline

```
  [ ON-PREMISE PACS / DICOM MODALITY ]
                 |
                 | DICOM C-STORE / STOW-RS over mTLS (TLS 1.3)
                 v
  [ INGESTION & DE-IDENTIFICATION BOUNDARY ]
  * Metadata Sanitization: DICOM PS 3.15 Annex E Basic Profile
  * UID Pseudonymization: Salted HMAC-SHA256 (Root: '2.25.')
  * Pixel PHI Redaction: Dual-Engine OCR text detection with >=15% dilation
  * Temporal Consistency: Salted patient day offset preserving RECIST deltas
                 |
                 v
  [ CRYPTOGRAPHIC STORAGE ENGINE ]
  * Envelope Encryption: Master KEK (FIPS HSM/KMS) + Ephemeral DEK (AES-256-GCM)
  * Format: MEDENC01 binary envelope with 96-bit IV and 128-bit GCM Auth Tag
  * Crypto-Shredding: Deleting study DEK mathematically erases the scan
                 |
                 v
  [ DEEP LEARNING INFERENCE SERVICE ]
  * Zero-Disk Plaintext Spooling: Decrypted directly into RAM buffer
  * Preprocessing: Photometric inversion (MONOCHROME1 -> MONOCHROME2) + Windowing
  * Model: EfficientNet-V2-S / ConvNeXt-V2 (Multi-label Sigmoid head)
  * Target Pathologies: Pneumonia, Cardiomegaly, Pleural Effusion, Pneumothorax, Atelectasis
  * Explainability: Grad-CAM gradient-weighted spatial saliency heatmap overlay
                 |
                 v
  [ IMMUTABLE AUDIT TRAIL ]
  * Structured JSON audit logging (ISO 8601 UTC timestamp, cert fingerprint, actor ID)
```

---

## Directory Layout

```
.
├── pyproject.toml              # Build config and dependency definitions
├── requirements.txt            # Production dependencies
├── SPEC.md                     # Complete architectural design specification
├── PLAN.md                     # Implementation plan and task roadmap
├── RESEARCH.md                 # Deep research brief on architectures & benchmarks
├── medshield/
│   ├── anonymization/          # DICOM PS 3.15 Annex E and pixel redaction
│   │   ├── metadata.py         # Tag purger, Safe Harbor cleaner
│   │   ├── uid_hasher.py       # Salted HMAC-SHA256 UID generator (2.25.x)
│   │   ├── date_shifter.py     # Deterministic patient-level date shifter
│   │   └── pixel_cleaner.py    # Text region detection & pixel blackout
│   ├── crypto/                 # Cryptographic envelope storage engine
│   │   ├── kms_provider.py     # Local/Cloud KMS Master Key manager
│   │   └── envelope.py         # MEDENC01 binary packer, AES-256-GCM cipher
│   ├── ml/                     # Deep learning & explainability engine
│   │   ├── model.py            # Thoracic multi-label classifier
│   │   ├── preprocessor.py     # 16-bit DICOM normalization & windowing
│   │   ├── explainability.py   # Grad-CAM heatmap computation & overlay
│   │   └── inference_engine.py # Clinical triage urgency & prediction orchestration
│   ├── storage/
│   │   └── encrypted_store.py  # Atomic encrypted object store
│   ├── api/                    # FastAPI Ingestion & DICOMweb Service
│   │   ├── app.py              # Application factory & router configuration
│   │   ├── middleware/         # mTLS auth and CERT-In audit logging
│   │   └── routes/             # STOW-RS upload, inference, and heatmaps
│   ├── utils/
│   │   ├── dicom_helpers.py    # Pixel array extraction & serialization
│   │   └── logging.py          # Structured JSON audit logging formatter
│   └── verification/           # Compliance scanning & security tests
│       ├── compliance_scanner.py # 18-tag HIPAA Safe Harbor auditor
│       └── entropy_analyzer.py   # Shannon entropy calculator (>= 7.99 bits/byte)
└── tests/                      # Automated test suite (28 tests, 100% pass)
```

---

## Running the Automated Test Suite

To run all unit and integration tests across the complete platform:

```powershell
python -m pytest tests/ -v
```

### Verified Test Cases:
- **`tests/test_config.py`**: Settings loader, secure defaults, structured audit logger.
- **`tests/test_metadata_anonymizer.py`**: Safe Harbor 18 tags removal, nested sequence cleaning, salted UID hashing (`2.25.x`), temporal date shifting.
- **`tests/test_pixel_cleaner.py`**: Burned-in text detection, $15\%$ bounding-box dilation, pixel matrix zeroing, `(0028,0301)` reset to `"NO"`.
- **`tests/test_crypto_envelope.py`**: KMS KEK/DEK generation, `MEDENC01` serialization, AES-256-GCM encryption/decryption, bit-level tamper rejection, crypto-shredding.
- **`tests/test_ml_inference.py`**: 16-bit DICOM normalization, MONOCHROME1 inversion, 5-class forward pass, Grad-CAM activation maps, triage urgency grading.
- **`tests/test_api_endpoints.py`**: mTLS client certificate validation, STOW-RS multipart upload, encrypted storage persistence, in-memory inference, Grad-CAM PNG generation.
- **`tests/test_compliance_e2e.py`**: Exhaustive HIPAA Safe Harbor audit scanner, Shannon entropy analysis ($\ge 7.99$ bits/byte), tamper resistance verification, crypto-shredding compliance.

---

## Launching the API Server

```powershell
uvicorn medshield.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Visit the interactive OpenAPI documentation at `http://localhost:8000/docs`.
