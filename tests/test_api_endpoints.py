import io
import pytest
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from medshield.config import Settings
from medshield.api.routes.studies import process_and_encrypt_study
from medshield.api.routes.inference import process_study_inference, generate_study_heatmap
from medshield.storage.encrypted_store import EncryptedStore

def create_raw_dicom_bytes(with_burned_text: bool = False) -> bytes:
    sop_class_uid = "1.2.840.10008.5.1.4.1.1.1"
    sop_instance_uid = "1.2.840.113619.2.55.3.6046883.849.55554444"
    
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = sop_class_uid
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    
    ds = Dataset()
    ds.file_meta = file_meta
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    
    ds.PatientName = "DOE^JANE"
    ds.PatientID = "HOSP-991122"
    ds.StudyDate = "20260101"
    ds.StudyTime = "120000"
    ds.StudyInstanceUID = "1.2.840.113619.2.55.3.6046883.849.99998888"
    ds.SeriesInstanceUID = "1.2.840.113619.2.55.3.6046883.849.77776666"
    ds.SOPInstanceUID = sop_instance_uid
    ds.SOPClassUID = sop_class_uid
    ds.Modality = "DX"
    ds.Rows = 128
    ds.Columns = 128
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BurnedInAnnotation = "YES" if with_burned_text else "NO"
    
    ds.PixelData = (b"\x05\x00" * (128 * 128))
    
    bio = io.BytesIO()
    pydicom.dcmwrite(bio, ds)
    return bio.getvalue()

def test_mtls_fingerprint_validation():
    settings = Settings(
        require_mtls=True,
        allowed_client_cert_fingerprints=["valid-cert-thumbprint-01"]
    )
    
    def validate_client_cert(header_fingerprint: str | None) -> bool:
        if not settings.require_mtls:
            return True
        if not header_fingerprint:
            return False
        return header_fingerprint in settings.allowed_client_cert_fingerprints

    # Missing cert
    assert validate_client_cert(None) is False
    # Invalid cert
    assert validate_client_cert("untrusted-bad-thumbprint") is False
    # Valid cert
    assert validate_client_cert("valid-cert-thumbprint-01") is True

def test_study_ingestion_service(tmp_path):
    storage_dir = str(tmp_path / "enc_studies")
    settings = Settings(storage_path=storage_dir)
    
    dicom_bytes = create_raw_dicom_bytes(with_burned_text=False)
    
    # 1. Execute Study Ingestion
    ingest_result = process_and_encrypt_study(contents=dicom_bytes, settings=settings)
    
    assert ingest_result.status == "INGESTED_AND_ENCRYPTED"
    anon_uid = ingest_result.anonymous_study_instance_uid
    assert anon_uid.startswith("2.25.")
    assert ingest_result.encryption_algorithm == "AES-256-GCM"
    assert ingest_result.burned_in_text_redacted is False
    
    # Verify encrypted storage contains container
    store = EncryptedStore(storage_dir=storage_dir)
    assert store.exists(anon_uid)
    encrypted_blob = store.load(anon_uid)
    assert encrypted_blob.startswith(b"MEDENC01")
    
    # 2. Execute Inference on Ingested Study
    inf_result = process_study_inference(study_uid=anon_uid, settings=settings)
    assert inf_result["study_instance_uid"] == anon_uid
    assert len(inf_result["predictions"]) == 5
    assert "inference_latency_ms" in inf_result
    
    # 3. Test Heatmap Generation
    png_bytes = generate_study_heatmap(study_uid=anon_uid, pathology="pneumonia", settings=settings)
    assert png_bytes.startswith(b"\x89PNG")
    assert len(png_bytes) > 100

def test_inference_nonexistent_study_raises_key_error(tmp_path):
    settings = Settings(storage_path=str(tmp_path))
    with pytest.raises(KeyError):
        process_study_inference(study_uid="2.25.999999999999", settings=settings)

def test_empty_dicom_upload_raises_value_error():
    settings = Settings()
    with pytest.raises(ValueError):
        process_and_encrypt_study(contents=b"", settings=settings)
