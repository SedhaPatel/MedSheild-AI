import io
import os
import pytest
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from medshield.config import Settings
from medshield.api.routes.studies import process_and_encrypt_study
from medshield.api.routes.inference import process_study_inference
from medshield.crypto.kms_provider import LocalKMSProvider, KeyRevokedError
from medshield.storage.encrypted_store import EncryptedStore
from medshield.verification.compliance_scanner import ComplianceScanner
from medshield.verification.entropy_analyzer import calculate_shannon_entropy

def create_synthetic_phi_study(patient_idx: int) -> bytes:
    sop_class_uid = "1.2.840.10008.5.1.4.1.1.1"
    sop_instance_uid = f"1.2.840.113619.2.55.3.6046883.849.{patient_idx}001"
    
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = sop_class_uid
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    
    ds = Dataset()
    ds.file_meta = file_meta
    
    # 18 HIPAA Safe Harbor PHI fields
    ds.PatientName = f"PATIENT_SURNAME^FIRSTNAME_{patient_idx}"
    ds.PatientID = f"MRN-{patient_idx:06d}"
    ds.PatientBirthDate = "19800520"
    ds.PatientSex = "F"
    ds.PatientAddress = f"{100 + patient_idx} Medical Center Blvd, Floor 3"
    ds.InstitutionName = "Apex Regional Health Hospital"
    ds.ReferringPhysicianName = "DR. ADAMS^ROBERT"
    ds.AccessionNumber = f"ACC-2026-{patient_idx:04d}"
    ds.StudyID = f"STU-{patient_idx:04d}"
    ds.StudyDate = "20260410"
    ds.StudyTime = "091530"
    ds.StudyInstanceUID = f"1.2.840.113619.2.55.3.6046883.849.{patient_idx}999"
    ds.SeriesInstanceUID = f"1.2.840.113619.2.55.3.6046883.849.{patient_idx}888"
    ds.SOPInstanceUID = sop_instance_uid
    ds.SOPClassUID = sop_class_uid
    
    # Clinical attributes (must be preserved)
    ds.Modality = "DX"
    ds.Rows = 128
    ds.Columns = 128
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BurnedInAnnotation = "NO"
    ds.PixelData = (b"\x10\x02" * (128 * 128))
    
    bio = io.BytesIO()
    pydicom.dcmwrite(bio, ds)
    return bio.getvalue()

def test_hipaa_safe_harbor_compliance_audit(tmp_path):
    storage_dir = str(tmp_path / "compliance_storage")
    settings = Settings(storage_path=storage_dir)
    scanner = ComplianceScanner()
    kms = LocalKMSProvider()
    store = EncryptedStore(storage_dir=storage_dir)
    
    # Ingest 3 distinct studies with heavy PHI
    for i in range(1, 4):
        raw_phi_dicom = create_synthetic_phi_study(i)
        
        # Verify pre-ingestion scanner catches the PHI
        pre_ds = pydicom.dcmread(io.BytesIO(raw_phi_dicom), force=True)
        pre_audit = scanner.scan_dataset(pre_ds)
        assert pre_audit.is_compliant is False
        assert len(pre_audit.violations) >= 5
        
        # Ingest and encrypt study
        ingest_res = process_and_encrypt_study(raw_phi_dicom, settings, kms=kms, store=store)
        anon_uid = ingest_res.anonymous_study_instance_uid
        
        # Recover decrypted dataset to audit the sanitized payload
        from medshield.crypto.envelope import decrypt_envelope
        enc_blob = store.load(anon_uid)
        plaintext_bytes = decrypt_envelope(enc_blob, kms)
        post_ds = pydicom.dcmread(io.BytesIO(plaintext_bytes), force=True)
        
        post_audit = scanner.scan_dataset(post_ds)
        assert post_audit.is_compliant is True, f"Violations found: {post_audit.violations}"
        assert len(post_audit.violations) == 0

def test_shannon_entropy_of_stored_ciphertexts(tmp_path):
    storage_dir = str(tmp_path / "entropy_storage")
    settings = Settings(storage_path=storage_dir)
    store = EncryptedStore(storage_dir=storage_dir)
    
    raw_dicom = create_synthetic_phi_study(1)
    res = process_and_encrypt_study(raw_dicom, settings, store=store)
    
    enc_blob = store.load(res.anonymous_study_instance_uid)
    # Exclude the 8-byte MEDENC01 header to measure ciphertext payload entropy
    ciphertext_payload = enc_blob[8:]
    entropy = calculate_shannon_entropy(ciphertext_payload)
    
    # High-grade AES-256-GCM ciphertext exhibits entropy >= 7.99 bits per byte
    assert entropy >= 7.99, f"Entropy too low ({entropy:.4f}), potential plaintext leak or poor PRNG!"

def test_tamper_resistance_verification(tmp_path):
    storage_dir = str(tmp_path / "tamper_storage")
    settings = Settings(storage_path=storage_dir)
    store = EncryptedStore(storage_dir=storage_dir)
    kms = LocalKMSProvider()
    
    raw_dicom = create_synthetic_phi_study(2)
    res = process_and_encrypt_study(raw_dicom, settings, kms=kms, store=store)
    anon_uid = res.anonymous_study_instance_uid
    
    # Tamper with the stored ciphertext
    enc_blob = bytearray(store.load(anon_uid))
    enc_blob[-5] ^= 0x42 # Flip bits in ciphertext
    store.save(anon_uid, bytes(enc_blob))
    
    # Decryption must fail completely
    with pytest.raises(PermissionError):
        process_study_inference(anon_uid, settings, kms=kms, store=store)

def test_crypto_shredding_dpdp_right_to_erasure(tmp_path):
    storage_dir = str(tmp_path / "shred_storage")
    settings = Settings(storage_path=storage_dir)
    store = EncryptedStore(storage_dir=storage_dir)
    kms = LocalKMSProvider()
    
    raw_dicom = create_synthetic_phi_study(3)
    res = process_and_encrypt_study(raw_dicom, settings, kms=kms, store=store)
    anon_uid = res.anonymous_study_instance_uid
    
    # Verify inference works initially
    inf_initial = process_study_inference(anon_uid, settings, kms=kms, store=store)
    assert len(inf_initial["predictions"]) == 5
    
    # Execute Crypto-Shredding: Revoke Master KEK
    kms.revoke_key(settings.kms_master_key_id)
    
    # Verification: Decryption is now mathematically impossible
    with pytest.raises(PermissionError):
        process_study_inference(anon_uid, settings, kms=kms, store=store)

