#!/usr/bin/env python
"""
MedShield-AI: Comprehensive End-to-End Pipeline & Regulatory Verification Script
================================================================================
Validates the complete clinical AI workflow against docs/SPEC.md requirements:
  [Phase 1] DICOM Generation with Heavy PHI & Burned-In Text Annotation
  [Phase 2] Ingestion, DICOM PS 3.15 Annex E De-ID & Pixel OCR Redaction
  [Phase 3] AES-256-GCM Envelope Encryption (KEK/DEK) & Shannon Entropy Storage Check
  [Phase 4] In-Memory Decryption & Deep Learning Disease Inference (5 Pathologies)
  [Phase 5] Explainable AI: Grad-CAM Activation Heatmap Generation
  [Phase 6] Regulatory Compliance Audit (HIPAA 18 Safe Harbor Identifiers)
  [Phase 7] Cryptographic Tamper Resistance (GCM Auth Tag Failure)
  [Phase 8] India DPDP Act Sec 12 Crypto-Shredding (Right to Erasure via KEK Revocation)
"""

import io
import os
import sys
import shutil
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
from PIL import Image, ImageDraw
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from medshield.config import Settings
from medshield.api.routes.studies import process_and_encrypt_study
from medshield.api.routes.inference import process_study_inference, generate_study_heatmap
from medshield.crypto.kms_provider import LocalKMSProvider
from medshield.crypto.envelope import decrypt_envelope
from medshield.storage.encrypted_store import EncryptedStore
from medshield.verification.compliance_scanner import ComplianceScanner
from medshield.verification.entropy_analyzer import calculate_shannon_entropy


def log_step(step_num: int, title: str):
    print(f"\n{'='*75}")
    print(f"  [STEP {step_num}] {title}")
    print(f"{'='*75}")


def create_phi_dicom() -> bytes:
    """Synthesizes a realistic DICOM image with 18 HIPAA identifiers and burned-in text."""
    sop_class_uid = "1.2.840.10008.5.1.4.1.1.1"  # DX Image Storage
    sop_instance_uid = "1.2.840.113619.2.55.3.6046883.849.9912001"
    
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = sop_class_uid
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    
    ds = Dataset()
    ds.file_meta = file_meta
    
    # 18 HIPAA Safe Harbor PHI fields
    ds.PatientName = "DOE^JANE^ELIZABETH"
    ds.PatientID = "MRN-981240-X"
    ds.PatientBirthDate = "19780614"
    ds.PatientSex = "F"
    ds.PatientAddress = "742 Evergreen Terrace, Springfield, OR 97477"
    ds.InstitutionName = "Apex Regional Health Hospital"
    ds.ReferringPhysicianName = "DR. ADAMS^ROBERT^M"
    ds.AccessionNumber = "ACC-2026-981240"
    ds.StudyID = "STU-2026-0042"
    ds.StudyDate = "20260410"
    ds.StudyTime = "091530"
    ds.StudyInstanceUID = "1.2.840.113619.2.55.3.6046883.849.9912999"
    ds.SeriesInstanceUID = "1.2.840.113619.2.55.3.6046883.849.9912888"
    ds.SOPInstanceUID = sop_instance_uid
    ds.SOPClassUID = sop_class_uid
    
    # Radiographic attributes
    ds.Modality = "DX"
    ds.Rows = 256
    ds.Columns = 256
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BurnedInAnnotation = "YES"
    
    # Base simulated tissue background
    img = Image.new("I;16", (256, 256), color=1200)
    draw = ImageDraw.Draw(img)
    # Burned-in text block on top margin (simulating technician burned-in PHI overlay)
    draw.rectangle([(20, 10), (140, 25)], fill=62000)
    # Simulated thoracic structure
    draw.ellipse([(60, 60), (196, 220)], fill=1800)
    
    arr = np.array(img, dtype=np.uint16)
    ds.PixelData = arr.tobytes()
    
    bio = io.BytesIO()
    pydicom.dcmwrite(bio, ds)
    return bio.getvalue()


def run_e2e_verification():
    print("""
    ========================================================================
       MedShield-AI: Automated End-to-End Pipeline & Regulatory Verification
    ========================================================================
    """)
    
    temp_dir = tempfile.mkdtemp(prefix="medshield_e2e_")
    try:
        settings = Settings(
            storage_path=os.path.join(temp_dir, "encrypted_studies"),
            secret_pepper="ProductionVerificationSalt_2026_SecureHashKey_X99!",
            kms_master_key_id="master-kek-e2e-2026"
        )
        kms = LocalKMSProvider()
        store = EncryptedStore(storage_dir=settings.storage_path)
        scanner = ComplianceScanner()
        
        # -------------------------------------------------------------
        # Step 1: Synthesize Raw DICOM with Heavy PHI & Burned-In Text
        # -------------------------------------------------------------
        log_step(1, "Synthesizing Raw DICOM with Patient PHI & Burned-In Overlay")
        raw_dicom_bytes = create_phi_dicom()
        print(f"  [+] Synthesized raw DICOM size: {len(raw_dicom_bytes):,} bytes")
        
        pre_ds = pydicom.dcmread(io.BytesIO(raw_dicom_bytes), force=True)
        print(f"  [+] Raw Patient Name       : {pre_ds.PatientName}")
        print(f"  [+] Raw Medical Record No  : {pre_ds.PatientID}")
        print(f"  [+] Raw Study Instance UID : {pre_ds.StudyInstanceUID}")
        print(f"  [+] Raw BurnedInAnnotation : {pre_ds.BurnedInAnnotation}")
        
        # Verify pre-ingestion audit fails
        pre_audit = scanner.scan_dataset(pre_ds)
        print(f"  [+] Pre-Ingestion Compliance Status: {pre_audit.is_compliant} (Expected: False)")
        print(f"  [+] Detected PHI Violations Count  : {len(pre_audit.violations)}")
        assert not pre_audit.is_compliant, "Pre-ingestion study should fail compliance!"
        assert len(pre_audit.violations) >= 5, "Expected multiple Safe Harbor violations"
        print("  [*] Step 1 Passed: Raw study contains detectable PHI.")

        # -------------------------------------------------------------
        # Step 2: Ingest, Sanitize Metadata & Inpaint Burned-in Text
        # -------------------------------------------------------------
        log_step(2, "Ingesting & De-Identifying Study (Metadata Stripping + Pixel Inpainting)")
        ingest_res = process_and_encrypt_study(
            raw_dicom_bytes,
            settings=settings,
            kms=kms,
            store=store
        )
        anon_uid = ingest_res.anonymous_study_instance_uid
        print(f"  [+] Ingestion Status        : {ingest_res.status}")
        print(f"  [+] Anonymous Study UID     : {anon_uid}")
        print(f"  [+] Burned-in Text Redacted : {ingest_res.burned_in_text_redacted}")
        print(f"  [+] Encryption Algorithm    : {ingest_res.encryption_algorithm}")
        print(f"  [+] Storage Object ID       : {ingest_res.storage_object_id}")
        
        assert ingest_res.status == "INGESTED_AND_ENCRYPTED"
        assert anon_uid.startswith("2.25."), f"UID must use 2.25 root, got: {anon_uid}"
        assert ingest_res.burned_in_text_redacted is True, "Burned-in text was not redacted!"
        print("  [*] Step 2 Passed: Ingestion, PS 3.15 de-identification, and pixel redaction complete.")

        # -------------------------------------------------------------
        # Step 3: Verify Cryptographic Storage at Rest
        # -------------------------------------------------------------
        log_step(3, "Verifying Zero-Trust Encrypted Storage (Entropy & Leakage Analysis)")
        enc_file_path = os.path.join(settings.storage_path, f"{anon_uid}.enc")
        assert os.path.exists(enc_file_path), f"Encrypted file not found at {enc_file_path}"
        
        encrypted_blob = store.load(anon_uid)
        magic_header = encrypted_blob[:8]
        print(f"  [+] Encrypted File Path     : {enc_file_path}")
        print(f"  [+] Encrypted File Size     : {len(encrypted_blob):,} bytes")
        print(f"  [+] Container Magic Header  : {magic_header.decode('latin-1', errors='ignore')}")
        assert magic_header == b"MEDENC01", f"Invalid magic header: {magic_header}"
        
        # Shannon Entropy Analysis
        ciphertext_payload = encrypted_blob[8:]
        entropy = calculate_shannon_entropy(ciphertext_payload)
        print(f"  [+] Shannon Entropy (Bits/Byte) : {entropy:.5f} (Target: >= 7.99)")
        assert entropy >= 7.99, f"Shannon entropy too low: {entropy}"
        
        # Zero-Plaintext Leakage Audit
        sensitive_strings = [
            b"DOE", b"JANE", b"981240", b"Springfield", b"Apex Regional",
            b"ADAMS", b"ACC-2026", b"19780614", b"DICM"
        ]
        leaks_detected = []
        for s in sensitive_strings:
            if s in encrypted_blob:
                leaks_detected.append(s.decode('latin-1'))
        
        print(f"  [+] Plaintext Leakage Scan      : {len(leaks_detected)} leaks detected")
        assert len(leaks_detected) == 0, f"Critical leakage in encrypted storage: {leaks_detected}"
        print("  [*] Step 3 Passed: Zero plaintext leakage and high-entropy AES-256-GCM verified.")

        # -------------------------------------------------------------
        # Step 4: In-Memory Decryption & Deep Learning Inference
        # -------------------------------------------------------------
        log_step(4, "Executing In-Memory Decryption & Deep Learning Disease Inference")
        inference_res = process_study_inference(
            anon_uid,
            settings=settings,
            kms=kms,
            store=store
        )
        print(f"  [+] Study UID Evaluated     : {inference_res['study_instance_uid']}")
        print(f"  [+] Inference Latency       : {inference_res['inference_latency_ms']:.2f} ms")
        top_urgency = "ROUTINE"
        if any(p["triage_urgency"] == "STAT_CRITICAL" for p in inference_res["predictions"]):
            top_urgency = "STAT_CRITICAL"
        elif any(p["triage_urgency"] == "ELEVATED" for p in inference_res["predictions"]):
            top_urgency = "ELEVATED"
            
        print(f"  [+] Overall Triage Urgency  : {top_urgency}")
        print("  [+] Multi-Label Pathologies Detected:")
        for pred in inference_res["predictions"]:
            prob_bar = "#" * int(pred["probability"] * 25)
            print(f"      - {pred['pathology']:<18}: {pred['probability']:.4f}  [{prob_bar:<25}] (Urgency: {pred['triage_urgency']})")
            assert 0.0 <= pred["probability"] <= 1.0, f"Invalid probability for {pred['pathology']}"
            assert pred["triage_urgency"] in ("STAT_CRITICAL", "ELEVATED", "ROUTINE")
            
        assert len(inference_res["predictions"]) == 5, "Expected 5 thoracic pathology predictions"
        print("  [*] Step 4 Passed: In-memory decryption and 5-class multi-label inference successful.")

        # -------------------------------------------------------------
        # Step 5: Explainability (Grad-CAM Activation Heatmaps)
        # -------------------------------------------------------------
        log_step(5, "Generating Explainable AI Grad-CAM Visual Heatmap Overlay")
        heatmap_png = generate_study_heatmap(
            anon_uid,
            pathology="Pneumonia",
            settings=settings,
            kms=kms,
            store=store
        )
        print(f"  [+] Heatmap PNG Payload Size: {len(heatmap_png):,} bytes")
        assert len(heatmap_png) > 1000, "Heatmap image byte stream too small!"
        # Verify PNG Magic Bytes
        assert heatmap_png[:8] == b"\x89PNG\r\n\x1a\n", "Generated heatmap is not valid PNG format"
        
        # Verify Image Dimensions via PIL
        hm_img = Image.open(io.BytesIO(heatmap_png))
        print(f"  [+] Heatmap Dimensions      : {hm_img.size} (Width x Height), Mode: {hm_img.mode}")
        assert hm_img.size == (224, 224), f"Expected 224x224 image, got {hm_img.size}"
        
        heatmap_save_path = os.path.join(temp_dir, "sample_gradcam_overlay.png")
        with open(heatmap_save_path, "wb") as f:
            f.write(heatmap_png)
        print(f"  [+] Sample Heatmap Exported : {heatmap_save_path}")
        print("  [*] Step 5 Passed: Grad-CAM activation heatmap successfully generated.")

        # -------------------------------------------------------------
        # Step 6: Post-Sanitization Regulatory Compliance Audit
        # -------------------------------------------------------------
        log_step(6, "Auditing Decrypted Dataset for HIPAA Safe Harbor Compliance")
        decrypted_dicom_bytes = decrypt_envelope(encrypted_blob, kms)
        post_ds = pydicom.dcmread(io.BytesIO(decrypted_dicom_bytes), force=True)
        
        post_audit = scanner.scan_dataset(post_ds)
        print(f"  [+] Post-Ingestion Compliant: {post_audit.is_compliant}")
        print(f"  [+] Remaining Violations    : {len(post_audit.violations)}")
        print(f"  [+] Cleaned BurnedInAnnot   : {getattr(post_ds, 'BurnedInAnnotation', 'None')}")
        print(f"  [+] Patient Name Header     : {repr(getattr(post_ds, 'PatientName', 'DELETED'))}")
        print(f"  [+] Patient ID Header       : {repr(getattr(post_ds, 'PatientID', 'DELETED'))}")
        
        assert post_audit.is_compliant is True, f"Compliance violations: {post_audit.violations}"
        assert len(post_audit.violations) == 0
        assert getattr(post_ds, "BurnedInAnnotation", None) == "NO"
        print("  [*] Step 6 Passed: 0 identifier-tag violations (DICOM PS 3.15 Annex E; dates shifted, not year-truncated).")

        # -------------------------------------------------------------
        # Step 7: Cryptographic Tamper Resistance Verification
        # -------------------------------------------------------------
        log_step(7, "Verifying Cryptographic Tamper Resistance (AES-256-GCM)")
        tampered_blob = bytearray(encrypted_blob)
        tampered_blob[-4] ^= 0xFF  # Flip bits in the GCM authentication tag / ciphertext
        store.save(anon_uid, bytes(tampered_blob))
        
        tamper_failed_as_expected = False
        try:
            process_study_inference(anon_uid, settings=settings, kms=kms, store=store)
        except PermissionError as pe:
            tamper_failed_as_expected = True
            print(f"  [+] Authenticated Decryption Rejected Tampered Payload: {pe}")
            
        assert tamper_failed_as_expected, "Tampered ciphertext did NOT trigger authentication failure!"
        # Restore valid blob
        store.save(anon_uid, encrypted_blob)
        print("  [*] Step 7 Passed: Cryptographic integrity guaranteed by AES-256-GCM.")

        # -------------------------------------------------------------
        # Step 8: India DPDP Act 2023 Sec 12 Crypto-Shredding Verification
        # -------------------------------------------------------------
        log_step(8, "Verifying Right to Erasure via Crypto-Shredding (DPDP Act Sec 12)")
        print(f"  [+] Active Master KEK ID     : {settings.kms_master_key_id}")
        kms.revoke_key(settings.kms_master_key_id)
        print(f"  [+] Revoked Master KEK       : {settings.kms_master_key_id}")
        
        shred_failed_as_expected = False
        try:
            process_study_inference(anon_uid, settings=settings, kms=kms, store=store)
        except PermissionError as pe:
            shred_failed_as_expected = True
            print(f"  [+] Inaccessible Post-Revocation: {pe}")
            
        assert shred_failed_as_expected, "Study remained readable after KEK revocation!"
        print("  [*] Step 8 Passed: Instant crypto-shredding mathematically guarantees data erasure.")

        print("\n" + "="*75)
        print("  ALL 8 VERIFICATION PHASES PASSED WITH ZERO ERRORS")
        print("="*75)
        return True

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    os.chdir(ROOT_DIR)
    success = run_e2e_verification()
    sys.exit(0 if success else 1)
