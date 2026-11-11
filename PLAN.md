# MedShield-AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify an end-to-end HIPAA- and India DPDP-compliant medical imaging system for thoracic disease detection from 2D chest radiographs, featuring DICOM PS 3.15 Annex E de-identification, automated OCR burned-in pixel redaction, AES-256-GCM envelope encryption with KEK/DEK separation, secure FastAPI upload/inference endpoints, and Grad-CAM explainability.

**Architecture:** Decoupled Zero-Trust pipeline where incoming DICOM studies are sanitized at the ingestion boundary (metadata stripped per PS 3.15 Annex E and pixel annotations redacted via dual-engine OCR), encrypted via AES-256-GCM envelope encryption using a mock/local KMS Key Encryption Key (KEK) and ephemeral per-study Data Encryption Keys (DEKs), ingested asynchronously via FastAPI STOW-RS endpoints, and passed to a deep learning inference engine (EfficientNet-V2 / ConvNeXt-V2) generating multi-label disease predictions and Grad-CAM heatmaps.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydicom, Cryptography (AES-256-GCM), PyTorch, Torchvision, ONNX Runtime, OpenCV, EasyOCR, NumPy, Pytest.

**Spec:** [`SPEC.md`](file:///d:/ISC-Project/SPEC.md)

---

## Global Constraints

- **Python Version:** Strictly Python 3.10+ (tested on Python 3.11).
- **Cryptographic Standard:** AES-256 in Galois/Counter Mode (GCM) with 96-bit unique IVs and 128-bit authentication tags; never CBC or ECB.
- **De-Identification Standard:** Strict DICOM PS 3.15 Annex E Basic Profile. All 18 HIPAA Safe Harbor metadata attributes must be sanitized.
- **Pixel Redaction Standard:** Any detected burned-in text bounding boxes must be dilated by $\ge 15\%$ and zero-filled (`0x0000`) before clearing tag `(0028,0301)`.
- **UID Format:** All de-identified Study, Series, and SOP Instance UIDs must be valid numeric dot-delimited strings ($\le 64$ chars) starting with registered prefix `2.25.`.
- **Zero In-Transit Plaintext:** All communication interfaces must simulate TLS 1.3 encryption; API endpoints must strictly validate simulated client-certificate headers and reject replayed tokens.
- **Test Coverage:** Every task must include unit/integration tests with $>90\%$ branch coverage for security and cryptographic modules.

---

## Review Focus

The five critical failure modes and edge cases identified from the spec that every task's tests must actively defend against:
1. **Partial Header De-Identification:** Nested sequence tags (e.g., `RequestAttributesSequence`, `SpecimenDescriptionSequence`) harboring hidden patient names or institutional identifiers that bypass top-level tag cleaners.
2. **Burned-In Text OCR False Negatives:** Low-contrast or rotated technician annotations along image borders leaking patient identity in the pixel raster matrix.
3. **Cryptographic Tag Tampering:** Subtle bit-level alteration in ciphertext or initialization vector (IV) during transit/storage failing to trigger immediate GCM authentication rejection.
4. **Longitudinal Study Desynchronization:** Follow-up studies for the same patient receiving disparate pseudorandom salts, destroying comparative clinical history.
5. **Key Management Leakage / Stale DEK RAM Residency:** Plaintext Data Encryption Keys (DEKs) lingering in process memory buffers following study encryption/decryption.

---

## Task Breakdown

### Task 1: Environment Setup & Project Core Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `medshield/__init__.py`
- Create: `medshield/config.py`
- Create: `medshield/utils/logging.py`
- Test: `tests/test_config.py`

**Step-by-step instructions:**
- [ ] **Step 1.1:** Create `pyproject.toml` and `requirements.txt` declaring project dependencies: `fastapi`, `uvicorn[standard]`, `pydicom`, `cryptography`, `opencv-python-headless`, `easyocr`, `torch`, `torchvision`, `numpy`, `pytest`, `pytest-asyncio`, `httpx`, `pillow`.
- [ ] **Step 1.2:** Write failing test `tests/test_config.py` verifying that environment configuration loads secure defaults: master KMS key path, DICOM upload directory, pepper salt for UID hashing, and log formatting.
- [ ] **Step 1.3:** Run `pytest tests/test_config.py` and confirm failure due to missing module.
- [ ] **Step 1.4:** Implement `medshield/config.py` using Pydantic Settings (`BaseSettings`) loading configuration from environment variables with secure fallbacks.
- [ ] **Step 1.5:** Implement `medshield/utils/logging.py` configuring structured JSON audit logging complying with CERT-In and HIPAA audit logging specs (capturing timestamp UTC, event type, actor ID, and IP).
- [ ] **Step 1.6:** Run `pytest tests/test_config.py` and verify all tests pass.

---

### Task 2: DICOM PS 3.15 Annex E Metadata De-Identification Engine

**Files:**
- Create: `medshield/anonymization/metadata.py`
- Create: `medshield/anonymization/uid_hasher.py`
- Create: `medshield/anonymization/date_shifter.py`
- Test: `tests/test_metadata_anonymizer.py`

**Step-by-step instructions:**
- [ ] **Step 2.1:** Write failing tests in `tests/test_metadata_anonymizer.py`:
  - Test top-level HIPAA 18 Safe Harbor tags are cleared/removed (`PatientName`, `PatientID`, `PatientBirthDate`, `AccessionNumber`, `InstitutionName`, etc.).
  - Test nested sequence tags (e.g. `AnatomicRegionSequence`, `OtherPatientIDsSequence`) are recursively purged of PHI.
  - Test salted UID pseudonymization: given an input UID and salt, produces a valid `2.25.` numeric dot-delimited UID that is deterministic for identical salts and disparate for different salts.
  - Test longitudinal date shifting: dates are shifted by a fixed patient offset, preserving exact hour/minute/second differences between series.
  - Test verification audit tags: `PatientIdentityRemoved (0012,0062)` set to `"YES"` and `DeidentificationMethodCodeSequence` added.
- [ ] **Step 2.2:** Run `pytest tests/test_metadata_anonymizer.py` and confirm failure.
- [ ] **Step 2.3:** Implement `medshield/anonymization/uid_hasher.py`:
  - `generate_pseudonymized_uid(original_uid: str, secret_salt: bytes) -> str`
  - Compute HMAC-SHA256, convert digest to integer string, prefix with `2.25.`, truncate to 64 chars.
- [ ] **Step 2.4:** Implement `medshield/anonymization/date_shifter.py`:
  - `compute_patient_day_offset(patient_id: str, master_pepper: bytes) -> int`
  - Shift `StudyDate`, `SeriesDate`, `AcquisitionDate` while keeping `StudyTime` consistent.
- [ ] **Step 2.5:** Implement `medshield/anonymization/metadata.py`:
  - Define `PS315_TAGS_TO_REMOVE` (Action X) and `PS315_TAGS_TO_ZERO` (Action Z).
  - Implement recursive traversal for DICOM sequences.
  - Replace UIDs (`StudyInstanceUID`, `SeriesInstanceUID`, `SOPInstanceUID`) using `uid_hasher`.
- [ ] **Step 2.6:** Run `pytest tests/test_metadata_anonymizer.py` and ensure $100\%$ of assertions pass.

---

### Task 3: Dual-Engine OCR Detection & Inpainting for Burned-In Pixel PHI

**Files:**
- Create: `medshield/anonymization/pixel_cleaner.py`
- Create: `medshield/utils/dicom_helpers.py`
- Test: `tests/test_pixel_cleaner.py`

**Step-by-step instructions:**
- [ ] **Step 3.1:** Write failing tests in `tests/test_pixel_cleaner.py`:
  - Generate a synthetic synthetic 16-bit grayscale DICOM frame with text rendered on the top-left margin ("DOE, JOHN - MRN: 948102").
  - Test OCR detector locates the text bounding box.
  - Test bounding box expansion by $15\%$ margin.
  - Test pixel redaction zeros out the bounding box area in the native pixel array.
  - Test that tag `BurnedInAnnotation (0028,0301)` is set to `"NO"`.
  - Test that an image without text is unmodified, with tag `(0028,0301)` updated to `"NO"`.
- [ ] **Step 3.2:** Run `pytest tests/test_pixel_cleaner.py` to confirm failure.
- [ ] **Step 3.3:** Implement `medshield/utils/dicom_helpers.py`:
  - Helper functions to extract normalized 8-bit/16-bit 2D NumPy image buffers from `pydicom.Dataset` respecting `RescaleSlope`, `RescaleIntercept`, and `PhotometricInterpretation` (`MONOCHROME1` vs `MONOCHROME2`).
- [ ] **Step 3.4:** Implement `medshield/anonymization/pixel_cleaner.py`:
  - `clean_pixel_annotations(dataset: pydicom.Dataset, confidence_threshold: float = 0.4) -> Tuple[pydicom.Dataset, bool]`
  - Use EasyOCR / OpenCV contour text region detection on top 15% and bottom 10% margins (and full scan if Secondary Capture modality).
  - Inpaint / blackout detected text regions with zero values directly in `dataset.PixelData`.
  - Update `dataset.BurnedInAnnotation = "NO"`.
- [ ] **Step 3.5:** Run `pytest tests/test_pixel_cleaner.py` and verify all tests pass.

---

### Task 4: AES-256-GCM Envelope Encryption & Cryptographic Storage Engine

**Files:**
- Create: `medshield/crypto/envelope.py`
- Create: `medshield/crypto/kms_provider.py`
- Create: `medshield/storage/encrypted_store.py`
- Test: `tests/test_crypto_envelope.py`

**Step-by-step instructions:**
- [ ] **Step 4.1:** Write failing tests in `tests/test_crypto_envelope.py`:
  - Test KEK generation and secure storage in Local/Mock KMS.
  - Test `GenerateDataKey` creates a 256-bit plaintext DEK and a KEK-encrypted ciphertext DEK.
  - Test `encrypt_dicom_bytes` outputs binary container adhering to `MEDENC01` format (Magic Bytes + KEK ID + Ciphertext DEK + 96-bit IV + 128-bit Tag + Ciphertext).
  - Test `decrypt_dicom_bytes` successfully recovers exact raw DICOM bytes.
  - Test tamper rejection: flipping a single bit in the ciphertext or IV raises `InvalidTagException` or cryptographic integrity error.
  - Test crypto-shredding: deleting the DEK or KEK renders the blob permanently undecryptable.
- [ ] **Step 4.2:** Run `pytest tests/test_crypto_envelope.py` and confirm failure.
- [ ] **Step 4.3:** Implement `medshield/crypto/kms_provider.py`:
  - `LocalKmsProvider` simulating AWS KMS / Azure Key Vault with Master KEK stored securely.
  - `generate_data_key(kek_id: str) -> Tuple[bytes, bytes]` (returns plaintext DEK and encrypted DEK).
  - `decrypt_data_key(kek_id: str, encrypted_dek: bytes) -> bytes`.
- [ ] **Step 4.4:** Implement `medshield/crypto/envelope.py`:
  - `encrypt_envelope(payload: bytes, plaintext_dek: bytes, kek_id: str, encrypted_dek: bytes) -> bytes`
  - Uses `AES.new(plaintext_dek, AES.MODE_GCM)`. Generates 12-byte random IV. Serializes with `MEDENC01` header.
  - `decrypt_envelope(container_bytes: bytes, kms: KmsProvider) -> bytes`.
- [ ] **Step 4.5:** Implement `medshield/storage/encrypted_store.py`:
  - Local filesystem or S3-compatible encrypted object storage backend with atomic writes.
- [ ] **Step 4.6:** Run `pytest tests/test_crypto_envelope.py` and verify all tests pass.

---

### Task 5: Deep Learning Disease Detection & Grad-CAM Interpretability Engine

**Files:**
- Create: `medshield/ml/model.py`
- Create: `medshield/ml/preprocessor.py`
- Create: `medshield/ml/explainability.py`
- Create: `medshield/ml/inference_engine.py`
- Test: `tests/test_ml_inference.py`

**Step-by-step instructions:**
- [ ] **Step 5.1:** Write failing tests in `tests/test_ml_inference.py`:
  - Test DICOM image preprocessing converts raw 16-bit pixel array to $3\times224\times224$ (or $3\times512\times512$) normalized float tensor with CLAHE (Contrast Limited Adaptive Histogram Equalization).
  - Test model forward pass outputs multi-label predictions across the 5 target thoracic classes (Pneumonia, Cardiomegaly, Pleural Effusion, Pneumothorax, Atelectasis) with values in range $[0.0, 1.0]$.
  - Test Grad-CAM generator extracts gradients from final convolutional feature layer and returns a $224\times224$ normalized saliency heatmap.
  - Test temperature scaling produces calibrated probabilities and epistemic uncertainty bounds.
- [ ] **Step 5.2:** Run `pytest tests/test_ml_inference.py` and confirm failure.
- [ ] **Step 5.3:** Implement `medshield/ml/preprocessor.py`:
  - Standardize window center/width (Hounsfield / optical density), invert `MONOCHROME1` to match standard `MONOCHROME2`, apply histogram equalization, resize, and normalize to ImageNet / CheXpert statistics.
- [ ] **Step 5.4:** Implement `medshield/ml/model.py`:
  - Factory supporting EfficientNet-V2-S and ConvNeXt-V2-Base architectures with 5-class multi-label sigmoid heads.
  - Provide both lightweight mock weights for deterministic CI/CD testing and model checkpoint loading capability for real weights.
- [ ] **Step 5.5:** Implement `medshield/ml/explainability.py`:
  - `GradCAM` class registering forward and backward hooks on the target layer. Computes channel-weighted spatial activations with ReLU.
- [ ] **Step 5.6:** Implement `medshield/ml/inference_engine.py`:
  - High-level interface: `predict_study(dicom_bytes: bytes) -> InferenceResult`.
- [ ] **Step 5.7:** Run `pytest tests/test_ml_inference.py` and verify all assertions pass.

---

### Task 6: Secure FastAPI Ingestion & DICOMweb Service (STOW-RS / Inference API)

**Files:**
- Create: `medshield/api/app.py`
- Create: `medshield/api/routes/studies.py`
- Create: `medshield/api/routes/inference.py`
- Create: `medshield/api/middleware/mtls_auth.py`
- Create: `medshield/api/middleware/audit_logger.py`
- Test: `tests/test_api_endpoints.py`

**Step-by-step instructions:**
- [ ] **Step 6.1:** Write failing tests in `tests/test_api_endpoints.py`:
  - Test `POST /api/v1/studies` (STOW-RS compatible): Uploads a test DICOM file; verifies it is de-identified, encrypted, and stored; returns anonymous study UID.
  - Test missing or invalid mTLS client certificate header / token returns `401 Unauthorized`.
  - Test `POST /api/v1/inference/{study_uid}`: Reads encrypted study from storage, decrypts in-memory, executes inference, and returns diagnostic JSON with predictions, triage urgency, and Grad-CAM heatmap URL.
  - Test `GET /api/v1/heatmaps/{study_uid}/{pathology}`: Returns visual PNG heatmap overlay.
  - Test audit log record generated for every request with client IP, certificate SHA256 thumbprint, and timestamp.
- [ ] **Step 6.2:** Run `pytest tests/test_api_endpoints.py` and confirm failure.
- [ ] **Step 6.3:** Implement `medshield/api/middleware/mtls_auth.py` and `audit_logger.py`:
  - Validates client certificate thumbprints and Bearer JWT authorization.
  - Emits CERT-In and HIPAA-compliant structured log events.
- [ ] **Step 6.4:** Implement `medshield/api/routes/studies.py`:
  - Multipart DICOM file upload handler.
  - Chains: Metadata De-ID $\to$ OCR Pixel Inpainting $\to$ AES-256-GCM Envelope Encryption $\to$ Object Storage.
- [ ] **Step 6.5:** Implement `medshield/api/routes/inference.py`:
  - Decrypts study using KMS DEK decryption $\to$ passes to `InferenceEngine` $\to$ formats response per `SPEC.md §5.2`.
- [ ] **Step 6.6:** Implement `medshield/api/app.py` registering routers and error handlers.
- [ ] **Step 6.7:** Run `pytest tests/test_api_endpoints.py` and verify all tests pass.

---

### Task 7: End-to-End Security Verification & HIPAA/DPDP Compliance Audit Suite

**Files:**
- Create: `medshield/verification/compliance_scanner.py`
- Create: `medshield/verification/entropy_analyzer.py`
- Test: `tests/test_compliance_e2e.py`

**Step-by-step instructions:**
- [ ] **Step 7.1:** Write failing tests in `tests/test_compliance_e2e.py`:
  - **HIPAA Safe Harbor Audit:** Ingest 10 synthetic DICOM studies containing varied combinations of the 18 Safe Harbor identifiers; scan the resulting stored/decrypted studies and assert 0 identifiers remain.
  - **Shannon Entropy Test:** Calculate Shannon entropy of the stored `.enc` files; assert entropy $> 7.99$ bits per byte (indistinguishable from pure random noise).
  - **Tamper Resistance Test:** Randomly alter 1 byte in the stored ciphertext; assert that decryption fails unconditionally and logs a security incident alert.
  - **Crypto-Shredding Verification Test:** Execute deletion of study DEK; verify that decryption fails and data recovery is mathematically impossible.
  - **Audit Retention Test:** Query audit log database; verify log format contains all required fields: timestamp (ISO 8601 UTC), actor ID, client cert fingerprint, study UID, and cryptographic action.
- [ ] **Step 7.2:** Run `pytest tests/test_compliance_e2e.py` and confirm failure.
- [ ] **Step 7.3:** Implement `medshield/verification/compliance_scanner.py`:
  - Exhaustive DICOM tag dictionary inspector checking against HIPAA Safe Harbor and DICOM PS 3.15 Annex E tag lists.
- [ ] **Step 7.4:** Implement `medshield/verification/entropy_analyzer.py`:
  - Shannon entropy calculation: $H(X) = -\sum_{i=1}^n P(x_i) \log_2 P(x_i)$.
- [ ] **Step 7.5:** Run `pytest tests/test_compliance_e2e.py` and confirm all end-to-end security and compliance tests pass.

---

## Verification Plan

### Automated Test Suite Execution
Execute the full test suite with coverage report:
```powershell
pytest --cov=medshield --cov-report=term-missing tests/
```
**Success Thresholds:**
- Overall test suite pass rate: $100\%$.
- Line coverage on `medshield/anonymization` and `medshield/crypto`: $\ge 95\%$.
- Zero HIPAA Safe Harbor tags detected in de-identified output.
- All stored binary payloads exhibit Shannon entropy $\ge 7.99$.

### Manual Verification & Demo Walkthrough
1. **DICOM Ingestion Demonstration:**
   - Launch FastAPI server: `uvicorn medshield.api.app:app --port 8000`.
   - Submit sample chest radiograph with burned-in patient text using curl with simulated mTLS headers.
   - Inspect stored `.enc` file in storage directory; verify raw text viewer displays binary noise with no recognizable DICOM strings (e.g. no "DICM" prefix, no patient name).
2. **Inference & Explainability Demonstration:**
   - Send inference request to `/api/v1/inference/{study_uid}`.
   - Verify diagnostic JSON response returns predicted probabilities for Pneumonia, Cardiomegaly, Pleural Effusion, Pneumothorax, and Atelectasis.
   - Open returned Grad-CAM heatmap PNG in browser/viewer; verify red/yellow attention highlights map directly to anatomical lung zones.
3. **Crypto-Shredding Demonstration:**
   - Invoke key revocation for the study DEK.
   - Retry inference request; verify server returns `403 Forbidden` / `CryptographicKeyRevokedException` and writes security incident log.

