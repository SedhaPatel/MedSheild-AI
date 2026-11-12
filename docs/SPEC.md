# System Design Specification: Secure AI-Powered Medical Image Disease Detection System (MedShield-AI)

---

## 1. System Vision & Problem Statement

Modern healthcare platforms require automated disease detection from medical imaging while enforcing zero-trust data protection guarantees. This specification establishes the architecture for **MedShield-AI**, an end-to-end clinical AI platform designed to ingest raw medical imaging studies, sanitize Protected Health Information (PHI) across metadata and pixel planes, store payloads via hardware-backed envelope encryption, and execute deep learning disease classification with explainable visual localization.

The platform is designed from inception to satisfy the technical mandates of both the **US Health Insurance Portability and Accountability Act (HIPAA)** and India's **Digital Personal Data Protection (DPDP) Act, 2023** alongside CERT-In cybersecurity directives.

---

## 2. Finalized Architectural Pillars

### Pillar 1: Clinical Modality & Diagnostic Target
- **Modality:** 2D Projection Thoracic Radiography (Chest X-Ray, Modalities: `CR`, `DX`).
- **Primary Diagnostic Target:** Multi-label thoracic disease triage, specifically:
  1. *Pneumonia* (alveolar consolidation / inflammatory infiltrates)
  2. *Cardiomegaly* (cardiothoracic ratio $> 0.50$)
  3. *Pleural Effusion* (costophrenic angle blunting)
  4. *Pneumothorax* (visceral pleural line visualization)
  5. *Atelectasis* (volume loss / linear opacity)
- **Clinical Rationale:** Chest radiography accounts for $>40\%$ of all hospital imaging volume. Rapid triage in emergency and intensive care workflows prevents diagnostic delay while handling standardized 2D pixel matrices ($2048 \times 2048$, 12-to-16-bit depth) that enable sub-second inference without prohibitive multi-gigabyte volumetric GPU memory bottlenecks.
- **Reference Benchmarks:** CheXpert (Stanford), NIH ChestX-ray14, and MIMIC-CXR.

### Pillar 2: Backend & Ingestion Framework
- **Core Runtime:** Python 3.11+ with **FastAPI** (asynchronous ASGI framework).
- **DICOM Protocols:**
  - `pydicom` for low-level element parsing, transfer syntax handling, and VR (Value Representation) transformation.
  - `pynetdicom` for DIMSE service support (`C-STORE`, `C-ECHO`).
  - Standardized **DICOMweb STOW-RS** (`POST /studies`) and **WADO-RS** (`GET /studies/{studyUID}`) endpoints over HTTP/2.
- **Async Processing:** Background task worker queue (Celery or FastAPI Async BackgroundTasks with Redis) for decoupled OCR text extraction and deep learning inference.

### Pillar 3: Deep Learning & Explainability Pipeline
- **Backbone Architecture:** **EfficientNet-V2-S** and **ConvNeXt-V2-Base**.
  - *EfficientNet-V2-S:* 21.5M parameters, progressive training resolution, optimized Fused-MBConv layers for $<10\text{ ms}$ inference on Tensor Cores.
  - *ConvNeXt-V2-Base:* Modernized ConvNet with $7\times7$ depthwise convolutions and Global Response Normalization (GRN), providing Transformer-level representation with strict convolutional translational equivariance.
- **Inference Engine:** PyTorch with ONNX Runtime (FP16 execution provider), enabling deterministic hardware execution.
- **Explainability:** **Grad-CAM (Gradient-weighted Class Activation Mapping)** computing gradients of the target pathology score relative to the final convolutional feature map ($\mathcal{A}^k$), outputting a normalized $2D$ heatmap interpolated to the native DICOM matrix.
- **Uncertainty & Calibration:** Temperature scaling with Monte Carlo dropout ($N=10$ stochastic forward passes) to generate epistemic uncertainty scores alongside softmax class probabilities.

### Pillar 4: Zero-Trust Security & Cryptographic Storage
- **De-Identification Engine:** Adheres to **DICOM PS 3.15 Annex E** (Basic Application Level Confidentiality Profile):
  - *Action X & Z:* Stripping of 18 HIPAA Safe Harbor tags (`PatientName`, `PatientID`, `InstitutionName`, `ReferringPhysicianName`, etc.).
  - *Action U:* Cryptographic pseudonymization of `StudyInstanceUID`, `SeriesInstanceUID`, and `SOPInstanceUID` using salted HMAC-SHA256 prefixed with private root `2.25.`.
  - *Clean Pixel Data (Option E.3.1):* Dual-stage OCR (CRAFT detector + Tesseract/EasyOCR) targeting ultrasound and secondary capture borders to blackout burned-in text. Sets `(0028,0301)` to `"NO"`.
  - *Date Shifting (Option E.3.4):* Salted patient-level day offset maintaining exact longitudinal intervals between comparative studies.
- **Envelope Encryption (Storage at Rest):**
  - **AES-256-GCM** (Galois/Counter Mode) with unique 96-bit IV and 128-bit authentication tag.
  - Hierarchical Key Separation:
    - *Master Key (KEK - Key Encryption Key):* Retained inside FIPS 140-3 HSM/KMS.
    - *Per-Study Key (DEK - Data Encryption Key):* Ephemeral 256-bit symmetric key generated via CSPRNG per study, encrypted by the KEK, and stored in the encrypted DICOM blob header.
  - *Crypto-Shredding:* Deleting the study DEK instantly renders the encrypted DICOM blob mathematically irrecoverable, fulfilling DPDP Section 12 Right to Erasure.
- **Transmission Security:**
  - **TLS 1.3** enforcing `TLS_AES_256_GCM_SHA384` with Ephemeral Diffie-Hellman (ECDHE X25519) forward secrecy.
  - **Mutual TLS (mTLS):** Required client-certificate validation for on-premise hospital edge routers.
  - **0-RTT Early Data:** Explicitly disabled on reverse proxies to block cryptographic replay attacks.

---

## 3. Regulatory Alignment Matrix

| Regulatory Provision | Statutory Requirement | MedShield-AI Technical Control |
| :--- | :--- | :--- |
| **HIPAA Security Rule §164.312(a)(2)(iv)** | Encryption and decryption of ePHI at rest | AES-256-GCM envelope encryption with KMS-backed KEKs and per-study DEKs. |
| **HIPAA Security Rule §164.312(e)(1)** | Guarding against unauthorized access in transit | TLS 1.3 with mandatory mTLS client certificates and 0-RTT disabled. |
| **HIPAA Privacy Rule §164.514(b)** | Safe Harbor de-identification (18 identifiers) | Automated DICOM PS 3.15 Annex E tag stripper + CRAFT/Tesseract pixel OCR inpainting. |
| **India DPDP Act 2023 Section 8(5)** | Implementation of reasonable security safeguards | Zero-trust enclave architecture, segregated pseudonym database, and FIPS 140-3 HSM storage. |
| **India DPDP Act 2023 Section 6(7)** | Consent Manager integration & verification | Validation of ABHA/DPBI-signed digital consent tokens prior to DICOM decryption. |
| **India DPDP Act 2023 Section 12** | Right to Correction and Erasure | Single-API cryptographic erasure (crypto-shredding) of study DEKs from the KMS. |
| **India CERT-In Directions 2022** | 6-Hour incident reporting & 180-day logs | Immutable audit trail (NTP-synchronized) logging all KMS decryption requests for 180+ days. |

---

## 4. System Architecture & Component Interactions

```
+---------------------------------------------------------------------------------------------------+
|                                  MEDSHIELD-AI SYSTEM ARCHITECTURE                                 |
+---------------------------------------------------------------------------------------------------+

  [ ON-PREMISE HOSPITAL EDGE ]
  +---------------------------------------------------------------+
  | PACS / DICOM Modality                                         |
  +---------------------------------------------------------------+
            |
            | DICOM C-STORE / STOW-RS over mTLS (TLS 1.3)
            v
  +---------------------------------------------------------------+
  | MedShield Edge Gateway                                        |
  | 1. Metadata De-ID (PS 3.15 Annex E)                           |
  | 2. Burned-In Text OCR Detection & Inpainting                  |
  | 3. Pseudonymize UIDs via HMAC-SHA256 (Salted)                 |
  +---------------------------------------------------------------+
            |
            | Authenticated HTTPS / DICOMweb STOW-RS
            v
+===================================================================================================+
  [ SECURE CLOUD / DMZ INGESTION CLUSTER ]

  +---------------------------------------------------------------+
  | Ingestion API (FastAPI Gateway)                               |
  | - Validates mTLS Client Certificate & JWT Bearer Token        |
  | - Verifies DICOM PS 3.15 Audit Tag (0012,0062 == YES)         |
  +---------------------------------------------------------------+
            |
            +-----------------------------------+
            | Calls GenerateDataKey(KEK_ID)     | Encrypts DICOM Blob via AES-256-GCM
            v                                   v
  +-----------------------+           +---------------------------------------------+
  | Cloud HSM / KMS Engine|           | Encrypted Object Storage (S3 / Blob)        |
  | - Master KEK (FIPS)   |           | - Header: [Encrypted DEK | 96-bit IV | Tag] |
  +-----------------------+           | - Payload: [Encrypted DICOM Bitstream]      |
            ^                         +---------------------------------------------+
            | Decrypt DEK                       |
            |                                   | Dispatches Task
            v                                   v
  +---------------------------------------------------------------+
  | ML Inference Service (Triton / ONNX Runtime / PyTorch)        |
  | 1. Decrypts DEK in-memory -> Decrypts DICOM in RAM buffer     |
  | 2. Pixel Preprocessing: Rescale slope/intercept, 1024x1024 CLAHE|
  | 3. Model Forward Pass: ConvNeXt-V2 / EfficientNet-V2-S        |
  | 4. Saliency Generator: Grad-CAM Feature Map Computation       |
  | 5. Output: Diagnostic JSON + Bounding Box / Heatmap Coordinates|
  +---------------------------------------------------------------+
            |
            +-----------------------------------+
            | Writes Audit Entry                | Writes Pseudonym Linkage
            v                                   v
  +-----------------------+           +---------------------------------------------+
  | Immutable Audit Store |           | Segregated Identity Enclave (PostgreSQL)    |
  | (180-Day WORM Logs)   |           | - Original MRN <-> Anonymous Study UID      |
  +-----------------------+           | - Encrypted with Separate FLE Master Key    |
                                      +---------------------------------------------+
+===================================================================================================+
```

---

## 5. Interface & Data Contracts

### 5.1 DICOM Upload Endpoint (STOW-RS Compatible)
- **Path:** `POST /api/v1/studies`
- **Headers:**
  - `Content-Type: multipart/related; type="application/dicom"`
  - `Authorization: Bearer <JWT_TOKEN>`
  - `X-Client-Cert-SHA256: <THUMBPRINT>`
- **Request:** Binary multipart stream containing one or more DICOM Part 10 instances.
- **Response:**
  ```json
  {
    "status": "INGESTED_AND_ENCRYPTED",
    "anonymous_study_instance_uid": "2.25.8492049182049182049182049182",
    "instances_processed": 1,
    "burned_in_text_redacted": true,
    "encryption_algorithm": "AES-256-GCM",
    "storage_object_id": "studies/2.25.8492049182049182049182049182.enc",
    "timestamp_utc": "2026-11-12T00:25:00Z"
  }
  ```

### 5.2 Inference Request & Response
- **Path:** `POST /api/v1/inference/{anonymous_study_instance_uid}`
- **Headers:** `Authorization: Bearer <JWT_TOKEN>`
- **Response:**
  ```json
  {
    "study_instance_uid": "2.25.8492049182049182049182049182",
    "model_name": "ConvNeXt-V2-Thoracic-Triage-v1",
    "model_checkpoint_sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "inference_latency_ms": 11.4,
    "predictions": [
      {
        "pathology": "Pneumothorax",
        "probability": 0.942,
        "epistemic_uncertainty": 0.031,
        "triage_urgency": "STAT_CRITICAL",
        "gradcam_heatmap_url": "/api/v1/heatmaps/2.25.8492049182049182049182049182/pneumothorax.png",
        "bounding_box_normalized": [0.12, 0.45, 0.38, 0.72]
      },
      {
        "pathology": "Pleural Effusion",
        "probability": 0.128,
        "epistemic_uncertainty": 0.022,
        "triage_urgency": "ROUTINE",
        "gradcam_heatmap_url": null,
        "bounding_box_normalized": null
      }
    ],
    "verification_signature": "MEQCIFq9uO3g...[ECDSA-P256-SHA256]"
  }
  ```

### 5.3 Encrypted Storage Container Format
The binary object saved to the storage backend packages the envelope header and ciphertext:
```
+-------------------------------------------------------------------------+
| Magic Bytes: "MEDENC01" (8 bytes)                                       |
+-------------------------------------------------------------------------+
| KEK Key Identifier Length (uint16) + KEK Key ID (UTF-8 string)          |
+-------------------------------------------------------------------------+
| Ciphertext DEK Length (uint16) + Ciphertext DEK (e.g. 64-128 bytes)     |
+-------------------------------------------------------------------------+
| GCM Initialization Vector (IV): 12 bytes (96 bits)                      |
+-------------------------------------------------------------------------+
| GCM Authentication Tag: 16 bytes (128 bits)                             |
+-------------------------------------------------------------------------+
| Ciphertext Payload Length (uint64)                                      |
+-------------------------------------------------------------------------+
| Encrypted DICOM Bitstream (variable length)                             |
+-------------------------------------------------------------------------+
```

---

## 6. Security & Verification Test Requirements

Every release must pass an automated validation suite executing:
1. **Safe Harbor Leakage Test:** Scan 100% of DICOM header tags against the 18 HIPAA Safe Harbor definitions. Ensure no string matching patient name, phone, email, SSN, or non-salt date remains.
2. **Pixel PHI OCR Redaction Test:** Inject synthetic burned-in patient names and MRNs onto 50 ultrasound/X-ray test frames; verify OCR detection rate $\ge 99\%$ and ensure all detected regions are zeroed/inpainted.
3. **Ciphertext Randomness & Tamper Test:** Validate that storage payloads fail decryption if a single bit in the ciphertext or IV is mutated (GCM auth tag mismatch). Verify entropy of stored payloads $\ge 7.99$ bits/byte.
4. **Replay Attack Resistance Test:** Verify that replaying a captured TLS 1.3 0-RTT handshake payload is rejected by the API proxy.
5. **Crypto-Shredding Verification:** Delete a test study's DEK from the key registry; verify that the encrypted DICOM file is rendered permanently undecryptable.

