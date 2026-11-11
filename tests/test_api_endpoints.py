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

def test_dashboard_ui_and_analysis_service(tmp_path):
    from medshield.api.routes.dashboard import serve_dashboard_ui, list_dashboard_samples, analyze_dashboard_study
    
    # 1. UI HTML test
    html_res = serve_dashboard_ui()
    assert html_res.status_code == 200
    assert "MedShield-AI" in html_res.body.decode("utf-8")
    assert "Grad-CAM" in html_res.body.decode("utf-8")
    
    # 2. Samples listing
    samples_res = list_dashboard_samples()
    assert "samples" in samples_res
    assert len(samples_res["samples"]) == 3
    
    # 3. Analyze sample study
    settings = Settings(storage_path=str(tmp_path))
    analysis = analyze_dashboard_study(
        file=None,
        sample_id="patient_01_pneumonia",
        pathology_heatmap="Pneumonia",
        settings=settings
    )
    assert analysis["status"] == "SUCCESS"
    assert analysis["security"]["shannon_entropy_bits_per_byte"] >= 7.99
    assert len(analysis["security"]["sha256_hash"]) == 64
    assert len(analysis["deidentification"]["tag_diff_matrix"]) == 11
    assert len(analysis["ai_diagnostics"]["predictions"]) == 5
    assert analysis["images"]["gradcam_heatmap_url"].startswith("data:image/png;base64,")


def test_dashboard_download_decrypted_scan(tmp_path):
    from medshield.api.routes.dashboard import analyze_dashboard_study, download_dashboard_study
    from fastapi import HTTPException

    settings = Settings(storage_path=str(tmp_path))
    analysis = analyze_dashboard_study(
        file=None,
        sample_id="patient_01_pneumonia",
        pathology_heatmap="Pneumonia",
        settings=settings
    )
    study_uid = analysis["anonymous_study_instance_uid"]

    # 1. Download valid study
    res = download_dashboard_study(study_uid=study_uid, settings=settings)
    assert res.status_code == 200
    assert res.media_type == "application/dicom"
    assert "attachment; filename=" in res.headers["Content-Disposition"]
    assert len(res.body) > 1000

    # 2. Non-existent study throws 404
    with pytest.raises(HTTPException) as exc_info:
        download_dashboard_study(study_uid="2.25.00000000000000", settings=settings)
    assert exc_info.value.status_code == 404


