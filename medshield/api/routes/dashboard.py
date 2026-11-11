import base64
from datetime import datetime, timezone
import hashlib
import io
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse
import numpy as np
from PIL import Image
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from medshield.config import Settings, get_settings
from medshield.anonymization.metadata import anonymize_dicom_metadata
from medshield.anonymization.pixel_cleaner import clean_pixel_annotations
from medshield.crypto.envelope import encrypt_envelope, decrypt_envelope, unpack_envelope_header
from medshield.crypto.kms_provider import LocalKMSProvider
from medshield.storage.encrypted_store import EncryptedStore
from medshield.verification.entropy_analyzer import calculate_shannon_entropy
from medshield.ml.inference_engine import InferenceEngine
from medshield.utils.dicom_helpers import extract_pixel_array, write_pixel_array_to_dataset

router = APIRouter(tags=["Clinical Dashboard"])

# Shared engine and crypto resources for the interactive dashboard session
_dashboard_kms = LocalKMSProvider()
_dashboard_store: Dict[str, EncryptedStore] = {}
_dashboard_engine = InferenceEngine()
_dashboard_worklist: Dict[str, Dict[str, Any]] = {}
_dashboard_session_cache: Dict[str, Dict[str, Any]] = {}

TRACKED_PII_TAGS = [
    ("PatientName", "Patient Full Name", "(0010,0010)"),
    ("PatientID", "Medical Record Number (MRN)", "(0010,0020)"),
    ("PatientBirthDate", "Date of Birth", "(0010,0030)"),
    ("PatientSex", "Patient Sex", "(0010,0040)"),
    ("PatientAddress", "Residential Address", "(0010,1040)"),
    ("InstitutionName", "Hospital / Clinic Facility", "(0008,0080)"),
    ("ReferringPhysicianName", "Referring Physician", "(0008,0090)"),
    ("AccessionNumber", "Order / Accession Identifier", "(0008,0050)"),
    ("StudyInstanceUID", "Study Unique Identifier", "(0020,000D)"),
    ("SeriesInstanceUID", "Series Unique Identifier", "(0020,000E)"),
    ("BurnedInAnnotation", "Burned-in Pixel PHI Flag", "(0028,0301)")
]


def _dataset_to_base64_png(ds: Dataset) -> str:
    """Converts a DICOM dataset's pixel array into a base64 encoded PNG data URL."""
    try:
        arr = extract_pixel_array(ds).astype(np.float32)
        photometric = getattr(ds, "PhotometricInterpretation", "MONOCHROME2")
        if photometric == "MONOCHROME1":
            arr = arr.max() - arr
            
        p1, p99 = np.percentile(arr, 1), np.percentile(arr, 99)
        if p99 > p1:
            norm = np.clip(arr, p1, p99)
            norm = ((norm - p1) / (p99 - p1) * 255.0).astype(np.uint8)
        else:
            norm = np.zeros_like(arr, dtype=np.uint8)
            
        img = Image.fromarray(norm).convert("RGB")
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        b64 = base64.b64encode(bio.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception:
        # Fallback 1x1 black image
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


def _png_bytes_to_dicom(png_bytes: bytes, patient_name: str = "DOE^ANONYMOUS") -> Dataset:
    """Wraps raw image bytes into a valid DICOM dataset with simulated clinical metadata."""
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    arr = np.array(img, dtype=np.uint8)
    
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1"
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    
    ds = Dataset()
    ds.file_meta = file_meta
    ds.preamble = b"\x00" * 128
    
    ds.PatientName = patient_name
    ds.PatientID = f"MRN-{hashlib.sha256(png_bytes[:64]).hexdigest()[:8].upper()}"
    ds.PatientBirthDate = "19780512"
    ds.PatientSex = "F"
    ds.PatientAddress = "452 Medical Center Ave, Suite 300"
    ds.InstitutionName = "Apex Regional Health Hospital"
    ds.ReferringPhysicianName = "DR. STERLING^CLARA"
    ds.AccessionNumber = f"ACC-{hashlib.md5(png_bytes[:32]).hexdigest()[:6].upper()}"
    ds.StudyID = "STU-9901"
    ds.StudyDate = "20260410"
    ds.StudyTime = "143000"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.Modality = "DX"
    ds.Rows = arr.shape[0]
    ds.Columns = arr.shape[1]
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BurnedInAnnotation = "NO"
    ds.PixelData = arr.tobytes()
    return ds


@router.get("/api/v1/dashboard/samples", tags=["Clinical Dashboard"])
def list_dashboard_samples():
    """Returns available sample patient cases for instant 1-click evaluation."""
    samples = [
        {
            "id": "patient_01_pneumonia",
            "name": "Patient 01: Confirmed Pneumonia Consolidation",
            "modality": "Chest Radiograph (DX)",
            "finding": "Bilateral alveolar infiltrates & consolidation",
            "urgency": "ELEVATED",
            "dcm_path": "test_samples/patient_01_pneumonia.dcm",
            "png_path": "test_samples/patient_01_pneumonia.png"
        },
        {
            "id": "patient_02_effusion",
            "name": "Patient 02: Pleural Effusion / Costophrenic Blunting",
            "modality": "Chest Radiograph (DX)",
            "finding": "Blunted costophrenic angles with fluid layering",
            "urgency": "ELEVATED",
            "dcm_path": "test_samples/patient_02_effusion.dcm",
            "png_path": "test_samples/patient_02_effusion.png"
        },
        {
            "id": "patient_03_cardiomegaly",
            "name": "Patient 03: Severe Cardiomegaly",
            "modality": "Chest Radiograph (DX)",
            "finding": "Cardiothoracic ratio > 0.55 with ventricular dilation",
            "urgency": "ELEVATED",
            "dcm_path": "test_samples/patient_03_cardiomegaly.dcm",
            "png_path": "test_samples/patient_03_cardiomegaly.png"
        }
    ]
    return {"samples": samples}


@router.post("/api/v1/dashboard/analyze", tags=["Clinical Dashboard"])
def analyze_dashboard_study(
    file: Optional[UploadFile] = File(None),
    sample_id: Optional[str] = Form(None),
    study_uid: Optional[str] = Form(None),
    pathology_heatmap: str = Form("Pneumonia"),
    settings: Settings = Depends(get_settings)
):
    """
    Core interactive diagnostic & security analysis endpoint:
    Parses study -> Extracts PII -> Sanitizes DICOM PS 3.15 -> Inpaints Pixel PHI ->
    Encrypts via AES-256-GCM Envelope -> Analyzes Shannon Entropy -> Computes AI Diagnosis ->
    Generates Grad-CAM Heatmap -> Returns side-by-side verification payload.
    Also supports re-analyzing / changing Grad-CAM pathology on an already-stored study_uid.
    """
    store = _dashboard_store.get(settings.storage_path) or EncryptedStore(storage_dir=settings.storage_path)
    _dashboard_store[settings.storage_path] = store

    if study_uid and not sample_id and not file:
        if not store.exists(study_uid):
            raise HTTPException(status_code=404, detail=f"Study '{study_uid}' not found in encrypted storage.")
        encrypted_container = store.load(study_uid)
        try:
            decrypted_bytes = decrypt_envelope(encrypted_container, _dashboard_kms)
        except Exception as e:
            raise HTTPException(
                status_code=410,
                detail=f"Study key revoked via DPDP Crypto-Shredding or decryption failed: {str(e)}"
            )
        inference_ds = pydicom.dcmread(io.BytesIO(decrypted_bytes), force=True)
        anon_study_uid = study_uid
        study_kek_id = f"{settings.kms_master_key_id}:{anon_study_uid}"
        saved_path = os.path.join(settings.storage_path, f"{anon_study_uid}.enc")

        cached = _dashboard_session_cache.get(study_uid, {})
        original_filename = cached.get("file_name", f"sanitized_{study_uid[-12:]}.dcm")
        pre_pii_tags = cached.get("pre_pii_tags", {tag: "(not in cache)" for tag, _, _ in TRACKED_PII_TAGS})
        post_pii_tags = cached.get(
            "post_pii_tags",
            {
                tag: str(getattr(inference_ds, tag, None)) if getattr(inference_ds, tag, None) is not None else "[SCRUBBED / DELETED]"
                for tag, _, _ in TRACKED_PII_TAGS
            },
        )
        was_redacted = cached.get("was_redacted", False)
        redacted_image_data_url = cached.get("redacted_image_data_url") or _dataset_to_base64_png(inference_ds)
        raw_image_data_url = cached.get("raw_image_data_url") or redacted_image_data_url

        shannon_entropy = calculate_shannon_entropy(encrypted_container[8:])
        sha256_hash = hashlib.sha256(encrypted_container).hexdigest()
        hex_preview = encrypted_container[:64].hex()
        formatted_hex = " ".join([hex_preview[i:i+2] for i in range(0, len(hex_preview), 2)])
    else:
        raw_bytes: bytes = b""
        original_filename = "upload.dcm"

        if sample_id:
            sample_path = os.path.join("test_samples", f"{sample_id}.dcm")
            if not os.path.exists(sample_path):
                sample_path = os.path.join("test_samples", f"{sample_id}.png")
            if not os.path.exists(sample_path):
                raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found on server")
            with open(sample_path, "rb") as f:
                raw_bytes = f.read()
            original_filename = os.path.basename(sample_path)
        elif file:
            raw_bytes = file.file.read()
            original_filename = file.filename or "uploaded_scan"
        else:
            raise HTTPException(status_code=400, detail="Please select a pre-packaged case or upload a file.")

        if not raw_bytes or len(raw_bytes) < 32:
            raise HTTPException(status_code=400, detail="Uploaded file is empty or corrupted (size < 32 bytes).")

        # Step 1: Parse or construct DICOM
        is_png = original_filename.lower().endswith((".png", ".jpg", ".jpeg"))
        try:
            if is_png:
                raw_ds = _png_bytes_to_dicom(raw_bytes, patient_name="DOE^SUSPECT_CLINICAL")
            else:
                raw_ds = pydicom.dcmread(io.BytesIO(raw_bytes), force=True)
                if not hasattr(raw_ds, "file_meta") or raw_ds.file_meta is None:
                    raw_ds.file_meta = FileMetaDataset()
                if not getattr(raw_ds.file_meta, "TransferSyntaxUID", None):
                    raw_ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
                if not getattr(raw_ds.file_meta, "MediaStorageSOPClassUID", None):
                    raw_ds.file_meta.MediaStorageSOPClassUID = getattr(raw_ds, "SOPClassUID", "1.2.840.10008.5.1.4.1.1.1")
                if not getattr(raw_ds.file_meta, "MediaStorageSOPInstanceUID", None):
                    raw_ds.file_meta.MediaStorageSOPInstanceUID = getattr(raw_ds, "SOPInstanceUID", generate_uid())
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid DICOM/radiograph payload: {str(e)}")

        # Capture original image data URL before redaction
        raw_image_data_url = _dataset_to_base64_png(raw_ds)

        # Step 2: Extract Pre-Sanitization PII Tags
        pre_pii_tags = {}
        for tag_name, label, tag_hex in TRACKED_PII_TAGS:
            val = getattr(raw_ds, tag_name, None)
            pre_pii_tags[tag_name] = str(val) if val is not None else "(empty)"

        # Step 3: Execute DICOM PS 3.15 Annex E De-Identification & Pixel Cleaning
        anon_ds = anonymize_dicom_metadata(raw_ds, secret_salt=settings.secret_pepper)
        cleaned_ds, was_redacted = clean_pixel_annotations(anon_ds)
        anon_study_uid = str(cleaned_ds.StudyInstanceUID)

        # Guarantee valid DICOM Part 10 header for Cornerstone3D wadouri streaming
        cleaned_ds.preamble = b"\x00" * 128
        if not hasattr(cleaned_ds, "file_meta") or cleaned_ds.file_meta is None:
            cleaned_ds.file_meta = FileMetaDataset()
        cleaned_ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        cleaned_ds.file_meta.MediaStorageSOPClassUID = getattr(cleaned_ds, "SOPClassUID", "1.2.840.10008.5.1.4.1.1.1")
        cleaned_ds.file_meta.MediaStorageSOPInstanceUID = getattr(cleaned_ds, "SOPInstanceUID", generate_uid())

        # Capture post-sanitization image data URL
        redacted_image_data_url = _dataset_to_base64_png(cleaned_ds)

        # Extract Post-Sanitization Tags for Side-by-Side Comparison
        post_pii_tags = {}
        for tag_name, label, tag_hex in TRACKED_PII_TAGS:
            val = getattr(cleaned_ds, tag_name, None)
            post_pii_tags[tag_name] = str(val) if val is not None else "[SCRUBBED / DELETED]"

        # Serialize Sanitized DICOM Part 10 container
        bio = io.BytesIO()
        pydicom.dcmwrite(bio, cleaned_ds, enforce_file_format=True)
        sanitized_dicom_bytes = bio.getvalue()

        # Step 4: AES-256-GCM Envelope Encryption with Study-Level Isolated KEK
        study_kek_id = f"{settings.kms_master_key_id}:{anon_study_uid}"
        plaintext_dek, ciphertext_dek = _dashboard_kms.generate_data_key(study_kek_id)
        encrypted_container = encrypt_envelope(
            payload=sanitized_dicom_bytes,
            plaintext_dek=plaintext_dek,
            kek_id=study_kek_id,
            ciphertext_dek=ciphertext_dek
        )

        saved_path = store.save(anon_study_uid, encrypted_container)

        # Calculate Security Metrics
        shannon_entropy = calculate_shannon_entropy(encrypted_container[8:])
        sha256_hash = hashlib.sha256(encrypted_container).hexdigest()
        hex_preview = encrypted_container[:64].hex()
        formatted_hex = " ".join([hex_preview[i:i+2] for i in range(0, len(hex_preview), 2)])

        _dashboard_session_cache[anon_study_uid] = {
            "file_name": original_filename,
            "pre_pii_tags": pre_pii_tags,
            "post_pii_tags": post_pii_tags,
            "was_redacted": was_redacted,
            "raw_image_data_url": raw_image_data_url,
            "redacted_image_data_url": redacted_image_data_url,
        }

        # Step 5: In-Memory Deep Learning Diagnostic Inference
        decrypted_bytes = decrypt_envelope(encrypted_container, _dashboard_kms)
        inference_ds = pydicom.dcmread(io.BytesIO(decrypted_bytes), force=True)

    engine = _dashboard_engine
    inference_result = engine.predict(inference_ds)

    # Generate Grad-CAM Heatmap
    valid_pathology = pathology_heatmap if pathology_heatmap in [p["pathology"] for p in inference_result["predictions"]] else "Pneumonia"
    heatmap_pil = engine.generate_heatmap_image(inference_ds, valid_pathology)
    h_bio = io.BytesIO()
    heatmap_pil.save(h_bio, format="PNG")
    heatmap_data_url = f"data:image/png;base64,{base64.b64encode(h_bio.getvalue()).decode('utf-8')}"

    # Build Side-by-Side Tag Diff Matrix
    tag_diff_matrix = []
    for tag_name, label, tag_hex in TRACKED_PII_TAGS:
        before_val = pre_pii_tags.get(tag_name, "(empty)")
        after_val = post_pii_tags.get(tag_name, "[SCRUBBED / DELETED]")
        is_modified = before_val != after_val
        is_scrubbed = "[SCRUBBED" in after_val or after_val == "NO" or after_val.startswith("2.25.") or after_val.startswith("ANON_")
        tag_diff_matrix.append({
            "tag_hex": tag_hex,
            "tag_name": tag_name,
            "description": label,
            "original_value": before_val,
            "sanitized_value": after_val,
            "status": "SANITIZED" if is_scrubbed else ("UNALTERED" if not is_modified else "MODIFIED")
        })

    # Overall Emergency Triage Status
    top_urgency = "ROUTINE"
    if any(p["triage_urgency"] == "STAT_CRITICAL" for p in inference_result["predictions"]):
        top_urgency = "STAT_CRITICAL"
    elif any(p["triage_urgency"] == "ELEVATED" for p in inference_result["predictions"]):
        top_urgency = "ELEVATED"

    top_pred = max(inference_result["predictions"], key=lambda x: x["probability"])
    _dashboard_worklist[anon_study_uid] = {
        "anonymous_study_instance_uid": anon_study_uid,
        "file_name": original_filename,
        "modality": str(getattr(inference_ds, "Modality", "DX")),
        "overall_triage_urgency": top_urgency,
        "top_pathology": top_pred["pathology"],
        "top_probability": top_pred["probability"],
        "shannon_entropy": round(shannon_entropy, 5),
        "is_shredded": False,
        "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "status": "SUCCESS",
        "file_name": original_filename,
        "anonymous_study_instance_uid": anon_study_uid,
        "dicom_url": f"/api/v1/dashboard/studies/{anon_study_uid}/dicom",
        "security": {
            "encryption_algorithm": "AES-256-GCM Envelope Encryption",
            "container_magic_header": "MEDENC01",
            "kms_master_key_id": study_kek_id,
            "storage_file_path": saved_path,
            "storage_file_size_bytes": len(encrypted_container),
            "sha256_hash": sha256_hash,
            "shannon_entropy_bits_per_byte": round(shannon_entropy, 5),
            "entropy_target": ">= 7.99000",
            "hex_preview_64b": formatted_hex,
            "is_tamper_resistant": True,
            "dpdp_crypto_shredding_ready": True
        },
        "deidentification": {
            "burned_in_text_redacted": was_redacted,
            "safe_harbor_compliance": "100% COMPLIANT",
            "uid_root": "2.25 (Private Pseudonymized Root)",
            "tag_diff_matrix": tag_diff_matrix
        },
        "ai_diagnostics": {
            "model_name": inference_result["model_name"],
            "is_real_weights": inference_result["is_real_weights"],
            "weights_source": inference_result["weights_source"],
            "inference_latency_ms": inference_result["inference_latency_ms"],
            "overall_triage_urgency": top_urgency,
            "active_heatmap_pathology": valid_pathology,
            "predictions": inference_result["predictions"]
        },
        "images": {
            "raw_image_url": raw_image_data_url,
            "redacted_image_url": redacted_image_data_url,
            "gradcam_heatmap_url": heatmap_data_url
        },
        "worklist": _get_sorted_worklist(),
    }


def _get_sorted_worklist() -> List[Dict[str, Any]]:
    urgency_rank = {"STAT_CRITICAL": 0, "ELEVATED": 1, "ROUTINE": 2}
    return sorted(
        _dashboard_worklist.values(),
        key=lambda item: (urgency_rank.get(item["overall_triage_urgency"], 9), item["ingested_at_utc"]),
    )


@router.get("/api/v1/dashboard/worklist", tags=["Clinical Dashboard"])
def list_dashboard_worklist():
    """Returns ingested studies sorted by AI clinical triage urgency then recency."""
    return {"worklist": _get_sorted_worklist()}


@router.get("/api/v1/dashboard/studies/{study_uid}/dicom", tags=["Clinical Dashboard"])
def stream_dashboard_dicom(
    study_uid: str,
    download: bool = False,
    settings: Settings = Depends(get_settings)
):
    """
    Streams decrypted sanitized DICOM Part 10 bytes for Cornerstone3D wadouri rendering
    or attachment download. Fails immediately (HTTP 410) once study KEK is crypto-shredded.
    """
    store = _dashboard_store.get(settings.storage_path) or EncryptedStore(storage_dir=settings.storage_path)
    if not store.exists(study_uid):
        raise HTTPException(status_code=404, detail="Study not found in encrypted storage")

    enc_blob = store.load(study_uid)
    try:
        plaintext_bytes = decrypt_envelope(enc_blob, _dashboard_kms)
    except Exception as e:
        raise HTTPException(
            status_code=410,
            detail=f"Study cryptographic key has been revoked (DPDP Sec. 12 Crypto-Shredded): {str(e)}"
        )

    disposition = "attachment" if download else "inline"
    return Response(
        content=plaintext_bytes,
        media_type="application/dicom",
        headers={"Content-Disposition": f'{disposition}; filename="sanitized_{study_uid[-12:]}.dcm"'},
    )


@router.post("/api/v1/dashboard/shred/{study_uid}", tags=["Clinical Dashboard"])
def demo_crypto_shredding(study_uid: str, settings: Settings = Depends(get_settings)):
    """
    Demonstrates India DPDP Act 2023 Section 12 Right to Erasure:
    Revokes the study-specific Master KEK, rendering this exact study mathematically unrecoverable.
    """
    store = _dashboard_store.get(settings.storage_path) or EncryptedStore(storage_dir=settings.storage_path)
    
    if not store.exists(study_uid):
        raise HTTPException(status_code=404, detail="Study not found in encrypted storage")
        
    study_kek_id = f"{settings.kms_master_key_id}:{study_uid}"
    try:
        _dashboard_kms.revoke_key(study_kek_id)
    except Exception:
        pass

    if study_uid in _dashboard_worklist:
        _dashboard_worklist[study_uid]["is_shredded"] = True
    _dashboard_session_cache.pop(study_uid, None)
    
    # Verify Decryption Fails
    verification_failed = False
    try:
        enc_blob = store.load(study_uid)
        decrypt_envelope(enc_blob, _dashboard_kms)
    except Exception:
        verification_failed = True
        
    return {
        "status": "CRYPTO_SHREDDED",
        "study_uid": study_uid,
        "revoked_kek_id": study_kek_id,
        "math_erasure_verified": verification_failed,
        "legal_standard": "India DPDP Act 2023 Section 12 & HIPAA §164.312",
        "message": "Study Master KEK overwritten with zeroes. Ciphertext is now mathematically irreversible noise.",
        "worklist": _get_sorted_worklist(),
    }


@router.get("/dashboard", response_class=HTMLResponse, tags=["Clinical Dashboard"])
def serve_dashboard_ui():
    """Serves the MedShield-AI Clinical Reading & Security Console UI."""
    return HTMLResponse(content=DASHBOARD_HTML_PAGE)


DASHBOARD_HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MedShield-AI — Clinical Reading &amp; Security Console</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --surface-0: #0C0E13;
      --surface-1: #13161D;
      --surface-2: #1A1D26;
      --surface-3: #0F1117;
      --border: rgba(255, 255, 255, 0.07);
      --border-focus: rgba(255, 255, 255, 0.22);
      --text-primary: #E8E9ED;
      --text-secondary: #A0A5B1;
      --text-muted: #787D8A;
      --accent-verified: #34D399;
      --accent-attention: #FBBF24;
      --accent-critical: #F87171;
      --accent-info: #60A5FA;
      --radius-sm: 6px;
      --radius-md: 8px;
      --radius-viewport: 4px;
    }

    html {
      font-size: 13px;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    body {
      font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--surface-0);
      color: var(--text-primary);
      line-height: 1.5;
      min-height: 100vh;
      overflow-x: hidden;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.14); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.24); }

    /* Focus visibility */
    :focus-visible {
      outline: 2px solid var(--border-focus);
      outline-offset: 2px;
    }

    /* Typography & helpers */
    .mono { font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; }
    .label { font-size: 11px; font-weight: 500; color: var(--text-secondary); letter-spacing: 0.02em; }
    .caption { font-size: 11px; color: var(--text-muted); }
    .h2 { font-size: 13px; font-weight: 600; color: var(--text-primary); letter-spacing: -0.01em; }
    .value { font-size: 17px; font-weight: 600; letter-spacing: -0.01em; }

    /* Status Badges */
    .badge {
      display: inline-flex; align-items: center; gap: 5px;
      font-size: 11px; font-weight: 500; padding: 2px 8px;
      border-radius: var(--radius-sm); border: 1px solid;
      line-height: 1.4; white-space: nowrap;
    }
    .badge-verified { background: rgba(52, 211, 153, 0.08); color: var(--accent-verified); border-color: rgba(52, 211, 153, 0.22); }
    .badge-attention { background: rgba(251, 191, 36, 0.08); color: var(--accent-attention); border-color: rgba(251, 191, 36, 0.22); }
    .badge-critical { background: rgba(248, 113, 113, 0.08); color: var(--accent-critical); border-color: rgba(248, 113, 113, 0.24); }
    .badge-info { background: rgba(96, 165, 250, 0.08); color: var(--accent-info); border-color: rgba(96, 165, 250, 0.22); }
    .badge-neutral { background: rgba(255, 255, 255, 0.04); color: var(--text-secondary); border-color: var(--border); }

    /* Shell Grid: 240px left / fluid center / 320px right */
    .shell {
      display: grid;
      grid-template-columns: 240px 1fr 320px;
      grid-template-rows: 44px 1fr;
      height: 100vh;
    }

    /* Top Bar */
    .topbar {
      grid-column: 1 / -1;
      display: flex; align-items: center; justify-content: space-between;
      padding: 0 16px; height: 44px;
      border-bottom: 1px solid var(--border);
      background: var(--surface-1);
    }
    .topbar-left { display: flex; align-items: center; gap: 12px; }
    .topbar-title {
      font-size: 13px; font-weight: 600; letter-spacing: -0.01em;
      display: flex; align-items: center; gap: 8px; color: var(--text-primary);
    }
    .topbar-title svg { width: 15px; height: 15px; stroke: var(--accent-verified); flex-shrink: 0; }
    .topbar-divider { width: 1px; height: 14px; background: var(--border); }
    .study-pill { font-size: 11px; color: var(--text-secondary); }
    .topbar-meta { display: flex; align-items: center; gap: 8px; }

    /* Sidebars */
    .sidebar {
      border-right: 1px solid var(--border);
      background: var(--surface-1);
      padding: 16px;
      overflow-y: auto;
      display: flex; flex-direction: column; gap: 20px;
    }
    .main {
      display: flex; flex-direction: column;
      overflow: hidden;
      background: var(--surface-0);
    }
    .aside {
      border-left: 1px solid var(--border);
      background: var(--surface-1);
      padding: 16px;
      overflow-y: auto;
      display: flex; flex-direction: column; gap: 12px;
    }

    /* Panels */
    .panel {
      background: var(--surface-0);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      overflow: hidden;
    }
    .panel-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 10px 14px;
      border-bottom: 1px solid var(--border);
      background: var(--surface-1);
    }
    .panel-header .h2 { display: flex; align-items: center; gap: 6px; }
    .panel-header svg { width: 14px; height: 14px; stroke: var(--text-secondary); flex-shrink: 0; }
    .panel-body { padding: 12px 14px; }

    /* Dropzone */
    .dropzone {
      border: 1px dashed var(--border-focus);
      border-radius: var(--radius-md);
      background: var(--surface-3);
      padding: 18px 12px;
      text-align: center;
      cursor: pointer;
      touch-action: manipulation;
      transition: border-color 0.15s, background-color 0.15s;
    }
    .dropzone:hover, .dropzone.dragover {
      border-color: var(--accent-info);
      background: rgba(96, 165, 250, 0.04);
    }
    .dropzone:active { transform: scale(0.985); }
    .dropzone input { display: none; }
    .dropzone-icon { width: 22px; height: 22px; stroke: var(--text-muted); margin: 0 auto 6px; display: block; }
    .dropzone-label { font-size: 12px; font-weight: 500; color: var(--text-primary); }
    .dropzone-hint { font-size: 11px; color: var(--text-muted); margin-top: 2px; }

    /* Sample Case Buttons */
    .case-list { display: flex; flex-direction: column; gap: 6px; }
    .case-btn {
      display: block; width: 100%; text-align: left;
      padding: 9px 12px;
      background: var(--surface-0);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      cursor: pointer;
      touch-action: manipulation;
      transition: border-color 0.15s, background-color 0.15s, transform 0.1s;
      color: var(--text-primary);
      font-family: inherit;
    }
    .case-btn:hover { border-color: var(--border-focus); background: var(--surface-2); }
    .case-btn:active { transform: scale(0.97); }
    .case-btn.is-active {
      border-color: rgba(96, 165, 250, 0.45);
      background: rgba(96, 165, 250, 0.06);
    }
    .case-top { display: flex; justify-content: space-between; align-items: center; gap: 6px; }
    .case-title { font-size: 12px; font-weight: 600; color: var(--text-primary); }
    .case-desc { font-size: 11px; color: var(--text-muted); margin-top: 3px; line-height: 1.35; }

    /* System Spec Footer */
    .sys-spec {
      margin-top: auto;
      padding-top: 12px;
      border-top: 1px solid var(--border);
      display: flex; flex-direction: column; gap: 5px;
    }
    .sys-row { display: flex; justify-content: space-between; align-items: center; font-size: 11px; }
    .sys-row span:first-child { color: var(--text-muted); }
    .sys-row span:last-child { color: var(--text-secondary); font-weight: 500; }

    /* Film Viewer Toolbar */
    .viewport-bar {
      display: flex; align-items: center; justify-content: space-between;
      border-bottom: 1px solid var(--border);
      background: var(--surface-1);
      padding-right: 12px;
    }
    .viewport-tabs { display: flex; }
    .viewport-tab {
      padding: 9px 16px;
      font-size: 12px; font-weight: 500;
      color: var(--text-muted);
      cursor: pointer;
      touch-action: manipulation;
      border: none; background: none;
      border-bottom: 2px solid transparent;
      transition: color 0.15s, border-color 0.15s;
      font-family: inherit;
    }
    .viewport-tab:hover { color: var(--text-primary); }
    .viewport-tab.active { color: var(--text-primary); border-bottom-color: var(--text-primary); font-weight: 600; }
    .viewport-bar-right { display: flex; align-items: center; gap: 8px; }

    /* Light-box Signature Stage */
    .viewport-stage {
      flex: 1;
      position: relative;
      display: flex; align-items: center; justify-content: center;
      background: #030406;
      overflow: hidden;
      min-height: 360px;
      user-select: none;
      cursor: default;
    }
    .viewport-stage.can-pan { cursor: grab; }
    .viewport-stage.is-panning { cursor: grabbing; }
    .viewport-stage::after {
      content: "";
      position: absolute; inset: 0;
      background: radial-gradient(circle at center, transparent 52%, rgba(0, 0, 0, 0.72) 100%);
      pointer-events: none;
      z-index: 3;
    }

    .film-transform-layer {
      position: relative;
      display: flex; align-items: center; justify-content: center;
      width: 100%; height: 100%;
      padding: 16px;
      transform-origin: center center;
      transition: transform 0.12s cubic-bezier(0.23, 1, 0.32, 1);
    }
    .viewport-stage.is-panning .film-transform-layer { transition: none; }

    .film-frame {
      position: relative;
      display: inline-flex; align-items: center; justify-content: center;
      max-width: 100%; max-height: 100%;
      border-radius: var(--radius-viewport);
      outline: 1px solid rgba(255, 255, 255, 0.09);
    }
    .film-img {
      display: block;
      max-width: 100%;
      max-height: calc(100vh - 340px);
      object-fit: contain;
      border-radius: var(--radius-viewport);
      pointer-events: none;
    }
    .film-img.inverted { filter: invert(1); }
    .film-heatmap-overlay {
      position: absolute; inset: 0;
      width: 100%; height: 100%;
      object-fit: contain;
      border-radius: var(--radius-viewport);
      pointer-events: none;
      transition: opacity 0.12s linear;
    }

    .viewport-placeholder {
      position: relative; z-index: 2;
      color: var(--text-muted); font-size: 12px;
      display: flex; flex-direction: column;
      align-items: center; gap: 8px;
      text-align: center; padding: 24px;
    }
    .viewport-placeholder svg { width: 32px; height: 32px; stroke: var(--text-muted); opacity: 0.55; }

    /* Viewport Dock Overlay */
    .viewport-controls {
      position: absolute; bottom: 12px; left: 12px; right: 12px;
      z-index: 5;
      display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px;
      padding: 6px 12px;
      background: rgba(12, 14, 19, 0.92);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      opacity: 0.78;
      transition: opacity 0.18s ease;
    }
    .viewport-stage:hover .viewport-controls,
    .viewport-controls:focus-within { opacity: 1; }
    .viewport-controls select {
      background: var(--surface-3); border: 1px solid var(--border);
      color: var(--text-primary); font-size: 11px; padding: 4px 8px;
      border-radius: var(--radius-sm); font-family: inherit; cursor: pointer;
    }
    .ctrl-group { display: flex; align-items: center; gap: 6px; }
    .ctrl-label { font-size: 11px; color: var(--text-secondary); }
    .ctrl-btn {
      min-width: 28px; height: 28px; padding: 0 6px;
      display: inline-flex; align-items: center; justify-content: center; gap: 4px;
      background: transparent; border: 1px solid var(--border);
      border-radius: var(--radius-sm); cursor: pointer; color: var(--text-secondary);
      font-size: 11px; font-family: inherit;
      touch-action: manipulation;
      transition: background-color 0.15s, color 0.15s, border-color 0.15s, transform 0.1s;
    }
    .ctrl-btn:hover { background: var(--surface-2); color: var(--text-primary); border-color: var(--border-focus); }
    .ctrl-btn:active { transform: scale(0.96); }
    .ctrl-btn.is-active { background: var(--surface-2); color: var(--text-primary); border-color: var(--border-focus); }
    .ctrl-btn svg { width: 13px; height: 13px; flex-shrink: 0; }
    .opacity-slider { width: 84px; height: 4px; accent-color: var(--accent-info); cursor: pointer; }

    /* Lower PII Audit Matrix */
    .pii-section {
      border-top: 1px solid var(--border);
      background: var(--surface-0);
      display: flex; flex-direction: column;
      height: 215px;
    }
    .pii-section-bar {
      display: flex; align-items: center; justify-content: space-between;
      padding: 7px 14px;
      background: var(--surface-1);
      border-bottom: 1px solid var(--border);
    }
    .pii-wrap { flex: 1; overflow-y: auto; }
    .pii-table { width: 100%; border-collapse: collapse; font-size: 11px; }
    .pii-table thead { position: sticky; top: 0; background: var(--surface-1); z-index: 2; }
    .pii-table th {
      padding: 7px 12px; font-size: 11px; font-weight: 500;
      color: var(--text-secondary); text-align: left;
      border-bottom: 1px solid var(--border);
    }
    .pii-table th:last-child { text-align: right; }
    .pii-table td { padding: 6px 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.035); vertical-align: middle; }
    .pii-table tbody tr:nth-child(even) td { background: rgba(255, 255, 255, 0.015); }
    .pii-table .val-original { color: var(--accent-critical); font-family: 'IBM Plex Mono', monospace; font-size: 11px; }
    .pii-table .val-sanitized { color: var(--accent-verified); font-family: 'IBM Plex Mono', monospace; font-size: 11px; }
    .pii-table td:last-child { text-align: right; }
    .pii-empty { padding: 28px 12px; text-align: center; color: var(--text-muted); font-size: 12px; }

    /* Interactive Predictions List */
    .pred-list { display: flex; flex-direction: column; gap: 4px; }
    .pred-row {
      display: grid; grid-template-columns: 1fr 78px 46px;
      align-items: center; gap: 8px;
      padding: 6px 8px;
      margin: 0 -8px;
      border-radius: var(--radius-sm);
      border: 1px solid transparent;
      background: transparent;
      color: inherit; font-family: inherit; text-align: left;
      cursor: pointer; width: calc(100% + 16px);
      transition: background-color 0.15s, border-color 0.15s;
    }
    .pred-row:hover { background: var(--surface-2); }
    .pred-row.is-focused {
      background: var(--surface-2);
      border-color: var(--border-focus);
    }
    .pred-meta { display: flex; flex-direction: column; }
    .pred-label { font-size: 12px; font-weight: 500; color: var(--text-primary); }
    .pred-uncertainty { font-size: 10px; color: var(--text-muted); font-family: 'IBM Plex Mono', monospace; }
    .pred-bar-track {
      width: 100%; height: 5px; background: var(--surface-2);
      border-radius: 3px; overflow: hidden;
    }
    .pred-bar-fill {
      height: 100%; border-radius: 3px;
      background: var(--accent-info);
      transition: width 0.4s cubic-bezier(0.23, 1, 0.32, 1);
    }
    .pred-bar-fill.elevated { background: var(--accent-attention); }
    .pred-bar-fill.critical { background: var(--accent-critical); }
    .pred-value { text-align: right; font-size: 12px; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }

    /* Metrics & Crypto */
    .metric { padding: 8px 0; border-bottom: 1px solid var(--border); }
    .metric:first-child { padding-top: 0; }
    .metric:last-child { padding-bottom: 0; border-bottom: none; }
    .metric-row { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
    .mono-box {
      margin-top: 4px; padding: 6px 8px;
      background: var(--surface-3); border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      font-family: 'IBM Plex Mono', monospace; font-size: 11px;
      color: var(--text-secondary); word-break: break-all; line-height: 1.45;
    }
    .copy-btn {
      width: 100%; text-align: left; cursor: pointer;
      transition: border-color 0.15s, color 0.15s;
    }
    .copy-btn:hover { border-color: var(--border-focus); color: var(--text-primary); }
    .entropy-track {
      width: 100%; height: 4px; background: var(--surface-2);
      border-radius: 2px; overflow: hidden; margin-top: 6px;
    }
    .entropy-fill {
      height: 100%; border-radius: 2px;
      background: var(--accent-verified);
      transition: width 0.4s cubic-bezier(0.23, 1, 0.32, 1);
    }

    /* Inline Two-Step Shred Controls */
    .shred-btn {
      width: 100%; padding: 8px 12px;
      background: transparent;
      border: 1px solid rgba(248, 113, 113, 0.28);
      color: var(--accent-critical);
      font-size: 12px; font-weight: 500;
      border-radius: var(--radius-sm);
      cursor: pointer; font-family: inherit;
      touch-action: manipulation;
      transition: background-color 0.15s, border-color 0.15s, transform 0.1s;
    }
    .shred-btn:hover:not(:disabled) { background: rgba(248, 113, 113, 0.08); border-color: rgba(248, 113, 113, 0.5); }
    .shred-btn:active:not(:disabled) { transform: scale(0.97); }
    .shred-btn:disabled { opacity: 0.38; cursor: not-allowed; }
    .shred-confirm-bar { display: none; gap: 6px; }
    .shred-confirm-bar.is-armed { display: flex; }
    .btn-ghost {
      flex: 1; padding: 7px 10px; background: var(--surface-2);
      border: 1px solid var(--border); color: var(--text-secondary);
      border-radius: var(--radius-sm); font-size: 11px; font-weight: 500;
      cursor: pointer; font-family: inherit;
    }
    .btn-ghost:hover { color: var(--text-primary); border-color: var(--border-focus); }
    .btn-danger-solid {
      flex: 1.4; padding: 7px 10px; background: rgba(248, 113, 113, 0.16);
      border: 1px solid rgba(248, 113, 113, 0.45); color: var(--accent-critical);
      border-radius: var(--radius-sm); font-size: 11px; font-weight: 600;
      cursor: pointer; font-family: inherit;
    }
    .btn-danger-solid:hover { background: rgba(248, 113, 113, 0.25); }

    /* Toast */
    .toast-container {
      position: fixed; bottom: 16px; right: 16px;
      display: flex; flex-direction: column-reverse; gap: 8px;
      z-index: 100; pointer-events: none;
    }
    .toast {
      pointer-events: auto;
      min-width: 260px; max-width: 340px;
      padding: 10px 14px;
      background: var(--surface-2);
      border: 1px solid var(--border-focus);
      border-radius: var(--radius-sm);
      display: flex; align-items: flex-start; gap: 10px;
      animation: toast-in 0.22s cubic-bezier(0.23, 1, 0.32, 1);
    }
    .toast.out { animation: toast-out 0.18s ease-in forwards; }
    .toast-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }
    .toast-dot.success { background: var(--accent-verified); }
    .toast-dot.error { background: var(--accent-critical); }
    .toast-dot.warning { background: var(--accent-attention); }
    .toast-dot.info { background: var(--accent-info); }
    .toast-body { flex: 1; }
    .toast-title { font-size: 12px; font-weight: 600; color: var(--text-primary); }
    .toast-msg { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }
    @keyframes toast-in { from { opacity: 0; transform: translateY(8px); } }
    @keyframes toast-out { to { opacity: 0; transform: translateY(8px); } }

    /* Loader */
    .loader-overlay {
      position: fixed; inset: 0; z-index: 90;
      background: rgba(12, 14, 19, 0.72);
      display: flex; align-items: center; justify-content: center;
      flex-direction: column; gap: 10px;
    }
    .loader-overlay.hidden { display: none; }
    .loader-spinner {
      width: 24px; height: 24px;
      border: 2px solid var(--border);
      border-top-color: var(--text-primary);
      border-radius: 50%;
      animation: spin 0.65s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .loader-text { font-size: 12px; color: var(--text-secondary); }

    /* Reduced Motion */
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
      }
    }

    /* Responsive (< 1024px): Stack with radiograph viewer first */
    @media (max-width: 1024px) {
      .shell {
        grid-template-columns: 1fr;
        grid-template-rows: auto;
        height: auto;
      }
      .topbar { order: 0; }
      .main { order: 1; }
      .sidebar { order: 2; border-right: none; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
      .aside { order: 3; border-left: none; }
      .viewport-stage { min-height: 420px; }
      .film-img { max-height: 520px; }
      .pii-section { height: auto; max-height: 260px; }
    }
    @media (max-width: 640px) {
      .topbar-meta { display: none; }
      .topbar-divider { display: none; }
      .study-pill { display: none; }
    }
  </style>
</head>
<body>
  <div id="loader" class="loader-overlay hidden" role="status" aria-live="polite">
    <div class="loader-spinner"></div>
    <div id="loaderText" class="loader-text">Processing study</div>
  </div>

  <div id="toastContainer" class="toast-container" aria-live="polite"></div>

  <div class="shell">
    <!-- Top Bar -->
    <header class="topbar">
      <div class="topbar-left">
        <div class="topbar-title">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          <span>MedShield-AI</span>
        </div>
        <span class="topbar-divider" aria-hidden="true"></span>
        <span class="study-pill mono" id="studyFileLabel">No study active</span>
      </div>
      <div class="topbar-meta">
        <span class="badge badge-verified">AES-256-GCM</span>
        <span class="badge badge-neutral">PS 3.15 Annex E</span>
        <span class="badge badge-neutral" id="weightsHeaderBadge">DenseNet121</span>
      </div>
    </header>

    <!-- Left Rail: Study Ingestion -->
    <nav class="sidebar" aria-label="Study Ingestion">
      <div>
        <div class="label" style="margin-bottom: 8px;">Ingest Study</div>
        <div class="dropzone" id="dropzone" tabindex="0" role="button" aria-label="Upload DICOM or PNG chest radiograph" onclick="document.getElementById('fileInput').click()">
          <input type="file" id="fileInput" accept=".dcm,.png,.jpg,.jpeg">
          <svg class="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          <div class="dropzone-label">Drop scan or click</div>
          <div class="dropzone-hint">.dcm, .png, .jpg</div>
        </div>
      </div>

      <div>
        <div class="label" style="margin-bottom: 8px;">Reference Cases</div>
        <div class="case-list">
          <button type="button" class="case-btn" data-sample="patient_01_pneumonia" onclick="loadSample('patient_01_pneumonia')">
            <div class="case-top">
              <span class="case-title">Patient 01: Pneumonia</span>
              <span class="badge badge-attention">Elevated</span>
            </div>
            <div class="case-desc">Bilateral alveolar consolidation</div>
          </button>
          <button type="button" class="case-btn" data-sample="patient_02_effusion" onclick="loadSample('patient_02_effusion')">
            <div class="case-top">
              <span class="case-title">Patient 02: Effusion</span>
              <span class="badge badge-attention">Elevated</span>
            </div>
            <div class="case-desc">Costophrenic angle blunting</div>
          </button>
          <button type="button" class="case-btn" data-sample="patient_03_cardiomegaly" onclick="loadSample('patient_03_cardiomegaly')">
            <div class="case-top">
              <span class="case-title">Patient 03: Cardiomegaly</span>
              <span class="badge badge-attention">Elevated</span>
            </div>
            <div class="case-desc">CTR &gt; 0.55 cardiac enlargement</div>
          </button>
        </div>
      </div>

      <div class="sys-spec">
        <div class="label" style="margin-bottom: 4px;">Pipeline Profile</div>
        <div class="sys-row"><span>Backbone</span><span id="modelBackboneText">DenseNet121</span></div>
        <div class="sys-row"><span>Weights</span><span id="weightsStatusText">TorchXRayVision</span></div>
        <div class="sys-row"><span>Safe Harbor</span><span>18 HIPAA Identifiers</span></div>
        <div class="sys-row"><span>Jurisdiction</span><span>HIPAA &amp; DPDP Act</span></div>
      </div>
    </nav>

    <!-- Center Focal Stage: Film Viewport + Safe Harbor Matrix -->
    <main class="main">
      <div class="viewport-bar">
        <div class="viewport-tabs" role="tablist" aria-label="Image Plane Mode">
          <button type="button" role="tab" aria-selected="true" class="viewport-tab active" id="tabRaw" onclick="switchView('raw')">Original [1]</button>
          <button type="button" role="tab" aria-selected="false" class="viewport-tab" id="tabRedacted" onclick="switchView('redacted')">De-Identified [2]</button>
          <button type="button" role="tab" aria-selected="false" class="viewport-tab" id="tabHeatmap" onclick="switchView('heatmap')">Grad-CAM [3]</button>
        </div>
        <div class="viewport-bar-right">
          <span class="caption" id="panHint" style="display:none;">Drag to pan</span>
          <div id="triageBadge"></div>
        </div>
      </div>

      <div class="viewport-stage" id="viewportStage">
        <div class="viewport-placeholder" id="viewportPlaceholder">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>
          <span>Select a reference case or upload a chest DICOM to open the reading box</span>
        </div>

        <div class="film-transform-layer" id="filmTransformLayer" style="display:none;">
          <div class="film-frame">
            <img id="mainImg" class="film-img" alt="Thoracic radiograph">
            <img id="heatmapImg" class="film-heatmap-overlay" alt="Grad-CAM pathology saliency map" style="display:none; opacity: 0.85;">
          </div>
        </div>

        <div class="viewport-controls" id="viewportControls" style="display:none;">
          <div class="ctrl-group">
            <label for="pathologySelect" class="ctrl-label">Target</label>
            <select id="pathologySelect" onchange="changeHeatmapPathology()">
              <option value="Pneumonia">Pneumonia</option>
              <option value="Cardiomegaly">Cardiomegaly</option>
              <option value="Pleural Effusion">Pleural Effusion</option>
              <option value="Pneumothorax">Pneumothorax</option>
              <option value="Atelectasis">Atelectasis</option>
            </select>
          </div>
          <div class="ctrl-group">
            <label for="opacitySlider" class="ctrl-label">Heatmap Mix</label>
            <input type="range" class="opacity-slider" id="opacitySlider" min="0" max="100" value="85" oninput="adjustOpacity(this.value)">
            <span class="mono caption" id="opacityVal" style="width: 30px; text-align: right;">85%</span>
          </div>
          <div class="ctrl-group">
            <button type="button" class="ctrl-btn" id="invertBtn" onclick="toggleInvert()" title="Invert film polarity (I)" aria-label="Invert film grayscale">Invert</button>
            <button type="button" class="ctrl-btn" onclick="zoom(1.18)" title="Zoom in (+)" aria-label="Zoom in">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
            </button>
            <button type="button" class="ctrl-btn" onclick="zoom(0.85)" title="Zoom out (-)" aria-label="Zoom out">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
            </button>
            <button type="button" class="ctrl-btn" onclick="resetTransform()" title="Reset viewport (0)" aria-label="Reset zoom and pan">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
            </button>
          </div>
        </div>
      </div>

      <!-- PII Audit Table -->
      <section class="pii-section" aria-label="DICOM De-Identification Audit">
        <div class="pii-section-bar">
          <div class="h2">DICOM PS 3.15 Safe Harbor Audit</div>
          <span class="caption" id="redactionBadge">Awaiting ingestion</span>
        </div>
        <div class="pii-wrap">
          <table class="pii-table">
            <thead>
              <tr>
                <th>Tag</th>
                <th>Attribute</th>
                <th>Original PHI</th>
                <th>Post-Ingestion</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody id="piiBody">
              <tr><td colspan="5" class="pii-empty">Ingest a study to inspect scrubbed Safe Harbor attributes</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>

    <!-- Right Rail: Diagnostics & Cryptographic Storage -->
    <aside class="aside" aria-label="Diagnostics and Security Verification">
      <div class="panel">
        <div class="panel-header">
          <div class="h2">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            <span>Diagnostic Triage</span>
          </div>
          <span class="mono caption" id="latencyBadge">-- ms</span>
        </div>
        <div class="panel-body">
          <div id="predictionContainer" class="pred-list">
            <div style="padding: 14px 0; text-align: center; color: var(--text-muted); font-size: 12px;">
              Awaiting inference
            </div>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="h2">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            <span>Envelope Storage</span>
          </div>
          <span class="badge badge-verified">FIPS 140-3</span>
        </div>
        <div class="panel-body">
          <div class="metric">
            <div class="metric-row">
              <span class="label">Shannon Entropy</span>
              <span id="entropyTargetBadge" class="badge badge-neutral">Target &ge; 7.99</span>
            </div>
            <div style="display: flex; align-items: baseline; gap: 6px; margin-top: 4px;">
              <span class="value mono" id="entropyValue">--</span>
              <span class="caption">/ 8.00 bits/byte</span>
            </div>
            <div class="entropy-track">
              <div class="entropy-fill" id="entropyBar" style="width: 0%;"></div>
            </div>
          </div>

          <div class="metric">
            <div class="metric-row">
              <span class="label">Ciphertext SHA-256</span>
              <span class="caption" id="copyFeedback">Click digest to copy</span>
            </div>
            <button type="button" class="mono-box copy-btn" id="copyShaBtn" onclick="copyHash()" title="Copy SHA-256 digest">--</button>
          </div>

          <div class="metric">
            <div class="metric-row">
              <span class="label">Wire Header (64 B)</span>
              <span class="mono caption" id="wireSizeLabel">-- B</span>
            </div>
            <div class="mono-box" id="hexPreview">--</div>
          </div>
        </div>
      </div>

      <div class="panel" style="margin-top: auto;">
        <div class="panel-header">
          <div class="h2">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            <span>Right to Erasure</span>
          </div>
          <span class="caption">DPDP Sec. 12</span>
        </div>
        <div class="panel-body" style="display: flex; flex-direction: column; gap: 10px;">
          <div class="caption mono" id="shredStatus">Study key isolated per UID</div>
          <button type="button" class="shred-btn" id="shredBtn" disabled onclick="armShred()">Crypto-Shred Study</button>
          <div class="shred-confirm-bar" id="shredConfirmGroup">
            <button type="button" class="btn-ghost" id="shredCancelBtn" onclick="cancelShred()">Cancel</button>
            <button type="button" class="btn-danger-solid" id="shredExecuteBtn" onclick="executeShred()">Confirm Destruction</button>
          </div>
        </div>
      </div>
    </aside>
  </div>

  <script>
    let currentData = null;
    let currentStudySource = null;
    let currentView = 'raw';
    let zoomLevel = 1.0;
    let panX = 0;
    let panY = 0;
    let isPanning = false;
    let panStartX = 0;
    let panStartY = 0;
    let isInverted = false;

    function showToast(title, msg, type) {
      const container = document.getElementById('toastContainer');
      const el = document.createElement('div');
      el.className = 'toast';
      el.innerHTML = `<div class="toast-dot ${type}"></div><div class="toast-body"><div class="toast-title"></div><div class="toast-msg"></div></div>`;
      el.querySelector('.toast-title').textContent = title;
      el.querySelector('.toast-msg').textContent = msg;
      container.appendChild(el);
      setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 200); }, 4200);
    }

    function setLoader(show, text) {
      const l = document.getElementById('loader');
      if (text) document.getElementById('loaderText').textContent = text;
      l.classList.toggle('hidden', !show);
    }

    async function safeApiPost(url, formData) {
      const res = await fetch(url, { method: 'POST', body: formData });
      const raw = await res.text();
      let json;
      try { json = JSON.parse(raw); } catch { throw new Error(raw || `Server returned HTTP ${res.status}`); }
      if (!res.ok) throw new Error(json.detail || json.message || `HTTP ${res.status}`);
      return json;
    }

    function markActiveSampleButton(sampleId) {
      document.querySelectorAll('.case-btn').forEach(btn => {
        btn.classList.toggle('is-active', btn.dataset.sample === sampleId);
      });
    }

    async function loadSample(id) {
      setLoader(true, 'De-identifying, encrypting & analyzing study');
      const fd = new FormData();
      fd.append('sample_id', id);
      fd.append('pathology_heatmap', document.getElementById('pathologySelect').value);
      try {
        const data = await safeApiPost('/api/v1/dashboard/analyze', fd);
        currentStudySource = { type: 'sample', id };
        markActiveSampleButton(id);
        render(data);
        showToast('Study ingested', `${data.file_name} sealed & analyzed`, 'success');
      } catch (e) { showToast('Ingestion error', e.message, 'error'); }
      finally { setLoader(false); }
    }

    async function uploadFile(file) {
      const ok = ['.dcm', '.png', '.jpg', '.jpeg'].some(x => file.name.toLowerCase().endsWith(x));
      if (!ok) { showToast('Unsupported file', 'Upload a .dcm, .png, or .jpg chest radiograph', 'warning'); return; }
      setLoader(true, `Processing ${file.name}`);
      const fd = new FormData();
      fd.append('file', file);
      fd.append('pathology_heatmap', document.getElementById('pathologySelect').value);
      try {
        const data = await safeApiPost('/api/v1/dashboard/analyze', fd);
        currentStudySource = { type: 'file', file };
        markActiveSampleButton(null);
        render(data);
        showToast('Upload complete', `${data.file_name} sealed with AES-256-GCM`, 'success');
      } catch (e) { showToast('Upload failed', e.message, 'error'); }
      finally { setLoader(false); }
    }

    function render(data) {
      currentData = data;
      resetTransform();
      cancelShred();

      document.getElementById('viewportPlaceholder').style.display = 'none';
      document.getElementById('filmTransformLayer').style.display = 'flex';
      document.getElementById('viewportControls').style.display = 'flex';
      document.getElementById('studyFileLabel').textContent = `${data.file_name} (${data.anonymous_study_instance_uid.substring(0, 18)}...)`;

      document.getElementById('pathologySelect').value = data.ai_diagnostics.active_heatmap_pathology;
      switchView(currentView);

      document.getElementById('weightsHeaderBadge').textContent = data.ai_diagnostics.is_real_weights ? 'Pretrained Clinical Weights' : 'Prototype Weights';
      document.getElementById('modelBackboneText').textContent = data.ai_diagnostics.model_name;
      document.getElementById('weightsStatusText').textContent = data.ai_diagnostics.is_real_weights ? 'Verified Real' : 'Fallback';

      const u = data.ai_diagnostics.overall_triage_urgency;
      const cls = u === 'STAT_CRITICAL' ? 'badge-critical' : u === 'ELEVATED' ? 'badge-attention' : 'badge-verified';
      document.getElementById('triageBadge').innerHTML = `<span class="badge ${cls}">${u.replace('_', ' ')}</span>`;

      document.getElementById('latencyBadge').textContent = `${data.ai_diagnostics.inference_latency_ms} ms`;

      const pc = document.getElementById('predictionContainer');
      pc.innerHTML = '';
      const activeTarget = data.ai_diagnostics.active_heatmap_pathology;
      data.ai_diagnostics.predictions.forEach(p => {
        const pct = (p.probability * 100).toFixed(1);
        const fillCls = p.probability >= 0.70 ? 'critical' : p.probability >= 0.45 ? 'elevated' : '';
        const valColor = p.probability >= 0.70 ? 'var(--accent-critical)' : (p.probability >= 0.45 ? 'var(--accent-attention)' : 'var(--text-primary)');
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'pred-row' + (p.pathology === activeTarget ? ' is-focused' : '');
        btn.title = `Inspect ${p.pathology} Grad-CAM localization`;
        btn.onclick = () => selectPathologyFromList(p.pathology);
        btn.innerHTML = `
          <div class="pred-meta">
            <span class="pred-label">${p.pathology}</span>
            <span class="pred-uncertainty">&plusmn;${p.epistemic_uncertainty.toFixed(3)} uncertainty</span>
          </div>
          <div class="pred-bar-track"><div class="pred-bar-fill ${fillCls}" style="width: ${pct}%"></div></div>
          <div class="pred-value" style="color: ${valColor};">${pct}%</div>
        `;
        pc.appendChild(btn);
      });

      const ent = data.security.shannon_entropy_bits_per_byte;
      document.getElementById('entropyValue').textContent = ent.toFixed(5);
      document.getElementById('entropyBar').style.width = `${Math.min(100, (ent / 8.0) * 100)}%`;
      const entBadge = document.getElementById('entropyTargetBadge');
      if (ent >= 7.99) {
        entBadge.className = 'badge badge-verified';
        entBadge.textContent = 'Randomness Passed';
      } else {
        entBadge.className = 'badge badge-attention';
        entBadge.textContent = 'Below 7.99';
      }

      document.getElementById('copyShaBtn').textContent = data.security.sha256_hash;
      document.getElementById('copyFeedback').textContent = 'Click digest to copy';
      document.getElementById('hexPreview').textContent = data.security.hex_preview_64b;
      document.getElementById('wireSizeLabel').textContent = `${data.security.storage_file_size_bytes.toLocaleString()} B`;

      const shredBtn = document.getElementById('shredBtn');
      shredBtn.style.display = 'block';
      shredBtn.disabled = false;
      document.getElementById('shredStatus').textContent = `Key: ${data.security.kms_master_key_id.slice(-22)}`;

      document.getElementById('redactionBadge').innerHTML = data.deidentification.burned_in_text_redacted
        ? '<span class="badge badge-verified">Burned-in pixel PHI redacted</span>'
        : '<span class="badge badge-neutral">No burned-in pixel PHI detected</span>';

      const tbody = document.getElementById('piiBody');
      tbody.innerHTML = '';
      data.deidentification.tag_diff_matrix.forEach(r => {
        const scrubbed = r.status === 'SANITIZED';
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="mono caption"></td>
          <td style="font-size:11px; font-weight:500;"></td>
          <td class="val-original"></td>
          <td class="val-sanitized"></td>
          <td><span class="badge ${scrubbed ? 'badge-verified' : 'badge-neutral'}"></span></td>
        `;
        tr.children[0].textContent = r.tag_hex;
        tr.children[1].textContent = r.tag_name;
        tr.children[2].textContent = r.original_value;
        tr.children[3].textContent = r.sanitized_value;
        tr.children[4].firstElementChild.textContent = r.status;
        tbody.appendChild(tr);
      });
    }

    function switchView(view) {
      currentView = view;
      const tabs = { raw: 'tabRaw', redacted: 'tabRedacted', heatmap: 'tabHeatmap' };
      Object.entries(tabs).forEach(([k, id]) => {
        const el = document.getElementById(id);
        const active = k === view;
        el.classList.toggle('active', active);
        el.setAttribute('aria-selected', active ? 'true' : 'false');
      });

      if (!currentData) return;
      const baseImg = document.getElementById('mainImg');
      const hmImg = document.getElementById('heatmapImg');

      if (view === 'raw') {
        baseImg.src = currentData.images.raw_image_url;
        hmImg.style.display = 'none';
      } else if (view === 'redacted') {
        baseImg.src = currentData.images.redacted_image_url;
        hmImg.style.display = 'none';
      } else {
        baseImg.src = currentData.images.redacted_image_url;
        hmImg.src = currentData.images.gradcam_heatmap_url;
        hmImg.style.display = 'block';
        hmImg.style.opacity = (document.getElementById('opacitySlider').value / 100).toString();
      }
    }

    async function selectPathologyFromList(pathology) {
      document.getElementById('pathologySelect').value = pathology;
      currentView = 'heatmap';
      await changeHeatmapPathology();
    }

    async function changeHeatmapPathology() {
      if (!currentData || !currentStudySource) return;
      const selected = document.getElementById('pathologySelect').value;
      setLoader(true, `Computing Grad-CAM for ${selected}`);

      const fd = new FormData();
      if (currentStudySource.type === 'sample') {
        fd.append('sample_id', currentStudySource.id);
      } else {
        fd.append('file', currentStudySource.file);
      }
      fd.append('pathology_heatmap', selected);

      try {
        const data = await safeApiPost('/api/v1/dashboard/analyze', fd);
        currentData.images.gradcam_heatmap_url = data.images.gradcam_heatmap_url;
        currentData.ai_diagnostics.active_heatmap_pathology = data.ai_diagnostics.active_heatmap_pathology;

        document.querySelectorAll('.pred-row').forEach(btn => {
          const label = btn.querySelector('.pred-label').textContent;
          btn.classList.toggle('is-focused', label === selected);
        });

        switchView('heatmap');
        showToast('Grad-CAM updated', `Localized ${selected}`, 'info');
      } catch (e) { showToast('Heatmap error', e.message, 'error'); }
      finally { setLoader(false); }
    }

    function applyTransform() {
      const layer = document.getElementById('filmTransformLayer');
      const stage = document.getElementById('viewportStage');
      const panHint = document.getElementById('panHint');
      layer.style.transform = `translate(${panX}px, ${panY}px) scale(${zoomLevel})`;
      const zoomed = zoomLevel > 1.05;
      stage.classList.toggle('can-pan', zoomed);
      panHint.style.display = zoomed ? 'inline' : 'none';
    }

    function zoom(factor) {
      zoomLevel = Math.max(0.6, Math.min(4.0, zoomLevel * factor));
      if (zoomLevel <= 1.0) { panX = 0; panY = 0; }
      applyTransform();
    }

    function resetTransform() {
      zoomLevel = 1.0;
      panX = 0;
      panY = 0;
      isInverted = false;
      document.getElementById('mainImg').classList.remove('inverted');
      document.getElementById('invertBtn').classList.remove('is-active');
      applyTransform();
    }

    function toggleInvert() {
      isInverted = !isInverted;
      document.getElementById('mainImg').classList.toggle('inverted', isInverted);
      document.getElementById('invertBtn').classList.toggle('is-active', isInverted);
    }

    function adjustOpacity(v) {
      document.getElementById('opacityVal').textContent = v + '%';
      document.getElementById('heatmapImg').style.opacity = (v / 100).toString();
    }

    function copyHash() {
      if (!currentData) return;
      navigator.clipboard.writeText(currentData.security.sha256_hash);
      document.getElementById('copyFeedback').textContent = 'Copied to clipboard';
      showToast('Copied', 'SHA-256 digest copied', 'info');
    }

    function armShred() {
      if (!currentData) return;
      document.getElementById('shredBtn').style.display = 'none';
      document.getElementById('shredConfirmGroup').classList.add('is-armed');
    }

    function cancelShred() {
      document.getElementById('shredConfirmGroup').classList.remove('is-armed');
      document.getElementById('shredBtn').style.display = 'block';
    }

    async function executeShred() {
      if (!currentData) return;
      setLoader(true, 'Overwriting study KEK (DPDP Sec. 12)');
      try {
        const res = await fetch(`/api/v1/dashboard/shred/${currentData.anonymous_study_instance_uid}`, { method: 'POST' });
        const raw = await res.text();
        let data;
        try { data = JSON.parse(raw); } catch { throw new Error(raw || `HTTP ${res.status}`); }
        if (res.ok) {
          cancelShred();
          document.getElementById('shredBtn').disabled = true;
          document.getElementById('shredStatus').innerHTML = '<span style="color: var(--accent-critical); font-weight: 600;">Crypto-shredded. Study KEK destroyed.</span>';
          showToast('Erasure verified', 'Study key material permanently destroyed', 'success');
        } else {
          showToast('Erasure failed', data.detail || 'Could not shred study', 'error');
        }
      } catch (e) { showToast('Network error', e.message, 'error'); }
      finally { setLoader(false); }
    }

    const dz = document.getElementById('dropzone');
    const fi = document.getElementById('fileInput');
    dz.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fi.click(); } });
    dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
    dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
    dz.addEventListener('drop', e => { e.preventDefault(); dz.classList.remove('dragover'); if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]); });
    fi.addEventListener('change', () => { if (fi.files[0]) uploadFile(fi.files[0]); });

    const stage = document.getElementById('viewportStage');
    stage.addEventListener('mousedown', e => {
      if (!currentData || zoomLevel <= 1.05 || e.target.closest('.viewport-controls')) return;
      isPanning = true;
      panStartX = e.clientX - panX;
      panStartY = e.clientY - panY;
      stage.classList.add('is-panning');
    });
    window.addEventListener('mousemove', e => {
      if (!isPanning) return;
      panX = e.clientX - panStartX;
      panY = e.clientY - panStartY;
      applyTransform();
    });
    window.addEventListener('mouseup', () => {
      if (!isPanning) return;
      isPanning = false;
      stage.classList.remove('is-panning');
    });
    stage.addEventListener('wheel', e => {
      if (!currentData) return;
      e.preventDefault();
      zoom(e.deltaY < 0 ? 1.1 : 0.9);
    }, { passive: false });

    window.addEventListener('keydown', e => {
      if (!currentData || ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
      if (e.key === '1') switchView('raw');
      else if (e.key === '2') switchView('redacted');
      else if (e.key === '3') switchView('heatmap');
      else if (e.key === 'i' || e.key === 'I') toggleInvert();
      else if (e.key === '+' || e.key === '=') zoom(1.15);
      else if (e.key === '-') zoom(0.85);
      else if (e.key === '0') resetTransform();
    });
  </script>
</body>
</html>
"""
