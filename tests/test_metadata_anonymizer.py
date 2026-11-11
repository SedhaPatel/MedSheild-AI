import pytest
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence

from medshield.anonymization.uid_hasher import generate_pseudonymized_uid
from medshield.anonymization.date_shifter import compute_patient_day_offset, shift_dicom_dates
from medshield.anonymization.metadata import anonymize_dicom_metadata, PS315_TAGS_TO_REMOVE, PS315_TAGS_TO_ZERO

def create_sample_dicom() -> Dataset:
    ds = Dataset()
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    
    # Identifiable Metadata (HIPAA Safe Harbor)
    ds.PatientName = "DOE^JOHN^A"
    ds.PatientID = "HOSPITAL-MRN-998877"
    ds.PatientBirthDate = "19750412"
    ds.PatientSex = "M"
    ds.PatientAge = "049Y"
    ds.PatientAddress = "123 Medical Center Drive, Suite 400"
    ds.InstitutionName = "Metro General Hospital"
    ds.InstitutionalDepartmentName = "Radiology Department"
    ds.ReferringPhysicianName = "DR. SMITH^ALICE"
    ds.AccessionNumber = "ACC-2026-001928"
    ds.StudyID = "STU-99201"
    
    # Dates and Times
    ds.StudyDate = "20260315"
    ds.SeriesDate = "20260315"
    ds.AcquisitionDate = "20260315"
    ds.StudyTime = "143022"
    ds.SeriesTime = "143210"
    
    # Original UIDs
    ds.StudyInstanceUID = "1.2.840.113619.2.55.3.6046883.849.1234567890"
    ds.SeriesInstanceUID = "1.2.840.113619.2.55.3.6046883.849.9876543210"
    ds.SOPInstanceUID = "1.2.840.113619.2.55.3.6046883.849.1122334455"
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.1" # Computed Radiography Image Storage
    
    # Clinical Metadata (Must be preserved)
    ds.Modality = "DX"
    ds.BodyPartExamined = "CHEST"
    ds.ViewPosition = "PA"
    ds.Rows = 2048
    ds.Columns = 2048
    ds.PixelSpacing = [0.143, 0.143]
    ds.SliceThickness = 1.0
    ds.KVP = 120.0
    ds.ExposureTime = 15
    ds.XRayTubeCurrent = 200
    
    # Nested Sequence with PHI
    seq_item = Dataset()
    seq_item.PatientName = "DOE^JOHN^A"
    seq_item.RequestedProcedureID = "PROC-998811"
    seq_item.ReasonForTheRequestedProcedure = "Persistent cough and dyspnea"
    ds.RequestAttributesSequence = Sequence([seq_item])
    
    return ds

def test_uid_hasher_format_and_determinism():
    salt1 = b"SecretPepperSalt123"
    salt2 = b"DifferentPepperSalt456"
    uid = "1.2.840.113619.2.55.3.6046883.849.1234567890"
    
    anon_uid1 = generate_pseudonymized_uid(uid, salt1)
    anon_uid2 = generate_pseudonymized_uid(uid, salt1)
    anon_uid3 = generate_pseudonymized_uid(uid, salt2)
    
    # Must start with private root 2.25.
    assert anon_uid1.startswith("2.25.")
    # Length <= 64 chars per DICOM standard
    assert len(anon_uid1) <= 64
    # Must contain only digits and dots
    assert all(c.isdigit() or c == '.' for c in anon_uid1)
    # Deterministic with identical salt
    assert anon_uid1 == anon_uid2
    # Distinct with different salt
    assert anon_uid1 != anon_uid3

def test_date_shifter_preserves_temporal_delta():
    pepper = b"MasterPepperKey123"
    patient_id = "HOSPITAL-MRN-998877"
    
    offset_days = compute_patient_day_offset(patient_id, pepper)
    assert -365 <= offset_days <= 365
    
    # Same patient gets identical offset
    offset_days_2 = compute_patient_day_offset(patient_id, pepper)
    assert offset_days == offset_days_2
    
    # Different patient gets different offset
    offset_other = compute_patient_day_offset("OTHER-PATIENT-112233", pepper)
    assert offset_days != offset_other
    
    ds = create_sample_dicom()
    original_study_date = ds.StudyDate
    shift_dicom_dates(ds, offset_days)
    
    assert ds.StudyDate != original_study_date
    assert len(ds.StudyDate) == 8 # YYYYMMDD format
    assert ds.StudyTime == "143022" # Time preserved

def test_metadata_anonymizer_removes_hipaa_safe_harbor():
    ds = create_sample_dicom()
    salt = b"MedShieldMasterTestSalt!"
    
    anonymized = anonymize_dicom_metadata(ds, secret_salt=salt)
    
    # Verify Safe Harbor stripped
    assert "PatientName" not in anonymized or anonymized.PatientName == ""
    assert "PatientAddress" not in anonymized
    assert "InstitutionName" not in anonymized
    assert "InstitutionalDepartmentName" not in anonymized
    assert "ReferringPhysicianName" not in anonymized
    
    # Verify nested sequence cleared
    assert len(anonymized.RequestAttributesSequence) == 1
    assert "PatientName" not in anonymized.RequestAttributesSequence[0]
    
    # Verify Clinical Tags Preserved
    assert anonymized.Modality == "DX"
    assert anonymized.Rows == 2048
    assert anonymized.Columns == 2048
    assert anonymized.PixelSpacing == [0.143, 0.143]
    assert anonymized.KVP == 120.0
    
    # Verify UIDs pseudonymized
    assert anonymized.StudyInstanceUID.startswith("2.25.")
    assert anonymized.SeriesInstanceUID.startswith("2.25.")
    assert anonymized.SOPInstanceUID.startswith("2.25.")
    assert anonymized.StudyInstanceUID != ds.StudyInstanceUID
    
    # Verify Audit Tags
    assert anonymized.PatientIdentityRemoved == "YES"
    assert "PS 3.15" in anonymized.DeidentificationMethod
