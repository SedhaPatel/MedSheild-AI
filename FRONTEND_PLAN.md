# Minimalist Clinical Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or superpowers:subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a clutter-free, hospital-grade 2-card clinical interface in `medshield/api/routes/dashboard.py` implementing progressive disclosure, zero crude alerts, and seamless backend integration.

**Architecture:** A single-page progressive disclosure workstation powered by Tailwind CSS 3.x and Lucide Icons. The interface presents a 56px top bar with security assurance, followed by two clean side-by-side cards: an interactive medical scan viewport with a Grad-CAM toggle on the left, and a clinical diagnosis summary with a collapsible DICOM audit drawer and download button on the right.

**Tech Stack:** FastAPI, HTML5/Canvas, Tailwind CSS 3.x CDN, Lucide Icons, Vanilla ES6+ JavaScript, Pytest.

**Spec:** [FRONTEND_SPEC.md](file:///d:/ISC-Project/FRONTEND_SPEC.md) & [.interface-design/system.md](file:///d:/ISC-Project/.interface-design/system.md)

## Global Constraints

- Strict minimalism: No sidebars, no fake analytics charts, no settings menus.
- Zero browser `alert()` popups: All notifications must use non-blocking floating toasts.
- Full backend parity: 100% match with `/api/v1/dashboard/analyze`, `/api/v1/dashboard/samples`, `/api/v1/dashboard/shred/{study_uid}`, and `/api/v1/dashboard/download/{study_uid}`.
- Progressive disclosure: Collapsible technical details (DICOM tag matrix & SHA-256 hash) hidden by default.

## Review Focus

1. **Non-JSON Server Errors:** FastAPI returning a 500 HTML/text response must not trigger a client `SyntaxError: Unexpected token 'I'`.
2. **Missing Sample Files:** Selecting a sample or uploading a file $< 32$ bytes must display a clean toast rather than crashing the viewport.
3. **Decryption Download on Shredded Studies:** Attempting to download a scan that has already been crypto-shredded must cleanly report `KeyRevokedError` via toast.
4. **Grad-CAM Toggle Transitions:** Toggling the AI heatmap must switch smoothly without image flickering or aspect ratio distortion.
5. **Key Isolation Integrity:** Crypto-shredding an active study must never revoke the global master KEK or break subsequent uploads.

---

### Task 1: Backend Scan Download Endpoint & Key Decryption Service

**Files:**
- Modify: `medshield/api/routes/dashboard.py`
- Test: `tests/test_api_endpoints.py`

**Interfaces:**
- Consumes: `_dashboard_store` (`EncryptedStore`), `_dashboard_kms` (`LocalKMSProvider`), `decrypt_envelope`
- Produces: `GET /api/v1/dashboard/download/{study_uid} -> Response(media_type="application/octet-stream", content=decrypted_bytes)`

- [ ] **Step 1: Write test for the download endpoint**

Add `test_dashboard_download_decrypted_scan` in `tests/test_api_endpoints.py` verifying that:
1. Ingesting a sample study creates an encrypted record.
2. `GET /api/v1/dashboard/download/{study_uid}` returns HTTP 200 with `Content-Disposition` header and valid decrypted bytes.
3. Requesting a non-existent study UID returns HTTP 404.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api_endpoints.py -k test_dashboard_download_decrypted_scan -v`  
Expected: FAIL with HTTP 404 (endpoint not implemented yet).

- [ ] **Step 3: Implement `download_dashboard_study` endpoint in `medshield/api/routes/dashboard.py`**

Add endpoint:
```python
@router.get("/api/v1/dashboard/download/{study_uid}", tags=["Clinical Dashboard"])
def download_dashboard_study(study_uid: str, settings: Settings = Depends(get_settings)):
    store = _dashboard_store.get(settings.storage_path) or EncryptedStore(storage_dir=settings.storage_path)
    if not store.exists(study_uid):
        raise HTTPException(status_code=404, detail="Study not found in encrypted storage")
    enc_blob = store.load(study_uid)
    try:
        decrypted_bytes = decrypt_envelope(enc_blob, _dashboard_kms)
    except Exception as e:
        raise HTTPException(status_code=410, detail=f"Study cannot be decrypted (possibly crypto-shredded): {str(e)}")
    
    return Response(
        content=decrypted_bytes,
        media_type="application/dicom",
        headers={"Content-Disposition": f'attachment; filename="sanitized_{study_uid[:12]}.dcm"'}
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api_endpoints.py -k test_dashboard_download_decrypted_scan -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add medshield/api/routes/dashboard.py tests/test_api_endpoints.py
git commit -m "feat(api): add decrypted scan download endpoint for clinical dashboard"
```

---

### Task 2: Defensive Client API & Floating Toast Scaffolding

**Files:**
- Modify: `medshield/api/routes/dashboard.py` (`DASHBOARD_HTML_PAGE` JavaScript section)

**Interfaces:**
- Produces: `showToast(title: string, message: string, type: 'success' | 'error' | 'info' | 'warning') -> void`
- Produces: `safeApiPost(url: string, formData: FormData) -> Promise<object>`

- [ ] **Step 1: Implement `showToast` in `DASHBOARD_HTML_PAGE`**

Build an animated toast container (`#toastContainer`) in the top-right corner supporting:
- Color-coded borders and Lucide icons (Emerald for success, Rose for error, Cyan for info, Amber for warning).
- Auto-dismiss after 4000ms with manual close button.
- Smooth CSS translation transitions (`transform: translateY(-8px)`).

- [ ] **Step 2: Implement `safeApiPost` with defensive parsing**

Ensure `safeApiPost` catches server exceptions, checks `res.ok`, decodes `await res.text()` defensively, and throws readable errors without triggering `SyntaxError`.

- [ ] **Step 3: Verify no `alert()` remains in the codebase**

Run regex search to confirm zero occurrences of `alert(` in `DASHBOARD_HTML_PAGE`.

- [ ] **Step 4: Commit**

```bash
git add medshield/api/routes/dashboard.py
git commit -m "feat(ui): add defensive api client and floating toast notification engine"
```

---

### Task 3: Top Navigation Bar & 2-Card Layout (Progressive Disclosure)

**Files:**
- Modify: `medshield/api/routes/dashboard.py` (`DASHBOARD_HTML_PAGE` HTML structure)

**Interfaces:**
- Produces: `#headerBar`, `#mainContainer` with `#cardLeft` (Scan Stage) and `#cardRight` (Clinical & Security Stage).

- [ ] **Step 1: Build Top Navigation Bar**

Implement fixed 56px header:
- MedShield-AI Shield logomark + title `MedShield-AI` + subtitle `Clinical Console`.
- Right-aligned security badge: `<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> System Secure (AES-256 / TLS 1.3)`.

- [ ] **Step 2: Build Card 1 Pre-Upload State**

Clean dashed dropzone:
- Cloud upload icon (`lucide-cloud-upload`).
- Primary text: `Drop DICOM (.dcm) or Scan (.png) here`.
- 3 quick sample chips: `Patient 01: Pneumonia`, `Patient 02: Effusion`, `Patient 03: Cardiomegaly`.

- [ ] **Step 3: Build Card 2 Awaiting State**

Clean placeholder card informing the clinician that diagnostic inference and cryptographic verification will appear as soon as a radiograph is loaded.

- [ ] **Step 4: Commit**

```bash
git add medshield/api/routes/dashboard.py
git commit -m "feat(ui): implement minimalist top bar and 2-card progressive disclosure layout"
```

---

### Task 4: Interactive Scan Viewport with Grad-CAM Heatmap Toggle

**Files:**
- Modify: `medshield/api/routes/dashboard.py` (`DASHBOARD_HTML_PAGE`)

**Interfaces:**
- Produces: `#scanViewport`, `#heatmapToggle`, `toggleHeatmap(enabled: boolean) -> void`

- [ ] **Step 1: Implement Active Scan Viewport in Card 1**

When study data loads:
- Hide dropzone prompt; display centered high-contrast radiograph `#scanImage` in `#000000` container.
- Preserve aspect ratio without letterboxing artifacts.

- [ ] **Step 2: Implement Single Heatmap Toggle Switch**

Add minimalist iOS/Tailwind toggle switch:
- Label: `Show AI Heatmap (Grad-CAM)`.
- When toggled ON: switch `src` to `data.images.gradcam_heatmap_url` (or blended overlay).
- When toggled OFF: revert `src` to `data.images.redacted_image_url`.

- [ ] **Step 3: Commit**

```bash
git add medshield/api/routes/dashboard.py
git commit -m "feat(ui): add clean radiograph stage with grad-cam heatmap toggle switch"
```

---

### Task 5: Clinical Diagnosis, Compact Security Badge & Collapsible Drawer

**Files:**
- Modify: `medshield/api/routes/dashboard.py` (`DASHBOARD_HTML_PAGE`)

**Interfaces:**
- Produces: `#primaryFinding`, `#confidenceBar`, `#securityBadge`, `#collapsibleDrawer`, `#downloadBtn`, `#shredBtn`

- [ ] **Step 1: Implement Primary AI Prediction Section**

- Large bold headline: Top disease finding name (`text-lg font-bold text-white`).
- Clean progress bar with gradient fill (`#06B6D4` $\rightarrow$ `#3B82F6`) and numeric percentage (`81.2% Confirmed`).
- Triage urgency pill (`ROUTINE`, `ELEVATED`, `STAT_CRITICAL`).
- Subtitle listing secondary screened findings in one quiet line.

- [ ] **Step 2: Implement Compact Security Badge**

- Emerald pill container: `PII Stripped • AES-256-GCM Encrypted` + `Entropy 7.999 / 8.000`.

- [ ] **Step 3: Implement Collapsible Drawer (`#auditDrawer`)**

- Accordion button: `[ ▾ View Stripped DICOM Tags & Hash ]` (collapsed by default).
- When clicked: smoothly expands to show:
  * Full SHA-256 ciphertext hash with 1-click clipboard copy button.
  * 18 Safe Harbor DICOM tag diff table (`PatientName`, `PatientID`, `DOB`, etc.).

- [ ] **Step 4: Implement Action Buttons**

- Primary button: `Download Decrypted Scan (.dcm)` calling `/api/v1/dashboard/download/{study_uid}`.
- Secondary button: `Crypto-Shred Study (DPDP Act)` calling `/api/v1/dashboard/shred/{study_uid}`.

- [ ] **Step 5: Commit**

```bash
git add medshield/api/routes/dashboard.py
git commit -m "feat(ui): implement clinical diagnosis, compact security badge, and audit drawer"
```

---

### Task 6: End-to-End Test Suite & Browser Verification

**Files:**
- Test: `tests/test_api_endpoints.py`
- Test: Probe script against `http://127.0.0.1:8000/dashboard`

- [ ] **Step 1: Run complete Pytest test suite**

Run: `python -m pytest tests/ -v`  
Expected: All 30 tests pass.

- [ ] **Step 2: End-to-End API probe**

Run Python script to verify:
1. `GET /dashboard` returns HTTP 200 with new minimalist DOM structure.
2. Ingesting `patient_01_pneumonia` returns SUCCESS.
3. `GET /api/v1/dashboard/download/{study_uid}` downloads valid decrypted DICOM bytes.
4. `POST /api/v1/dashboard/shred/{study_uid}` executes DPDP Act erasure.

- [ ] **Step 3: Final Git Commit**

```bash
git add .
git commit -m "feat: complete minimalist 2-card clinical workstation implementation"
```

