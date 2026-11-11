import io
from datetime import datetime, timezone
import pydicom
from pydicom.dataset import FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from medshield.config import Settings, get_settings
from medshield.anonymization.metadata import anonymize_dicom_metadata
from medshield.anonymization.pixel_cleaner import clean_pixel_annotations
from medshield.crypto.envelope import encrypt_envelope
from medshield.crypto.kms_provider import KMSProvider, LocalKMSProvider
from medshield.storage.encrypted_store import EncryptedStore
from medshield.utils.logging import get_audit_logger

router = APIRouter(prefix="/api/v1/studies", tags=["Studies Ingestion"])
audit_logger = get_audit_logger("medshield.audit.studies")

_shared_kms = LocalKMSProvider()
_shared_store: dict = {}

class IngestionResponse(BaseModel):
    status: str
    anonymous_study_instance_uid: str
    instances_processed: int
    burned_in_text_redacted: bool
    encryption_algorithm: str
    storage_object_id: str
    timestamp_utc: str

def process_and_encrypt_study(
    contents: bytes,
    settings: Settings,
    kms: KMSProvider = None,
    store: EncryptedStore = None
) -> IngestionResponse:
    """
    Core synchronous service pipeline:
    DICOM Parse -> PS 3.15 Annex E Metadata De-ID -> Pixel PHI OCR Redaction ->
    AES-256-GCM Envelope Encryption -> Encrypted Storage Persistence.
    """
    if not contents:
        raise ValueError("Uploaded file is empty")
        
    try:
        ds = pydicom.dcmread(io.BytesIO(contents), force=True)
    except Exception as e:
        raise ValueError(f"Failed to parse DICOM: {str(e)}")
        
    # 1. Metadata De-Identification (PS 3.15 Annex E + Salted UIDs)
    anon_ds = anonymize_dicom_metadata(ds, secret_salt=settings.secret_pepper)
    anon_study_uid = anon_ds.StudyInstanceUID
    
    # 2. Pixel De-Identification (Burned-in PHI detection + redaction)
    cleaned_ds, was_redacted = clean_pixel_annotations(anon_ds)
    
    # Ensure valid file_meta for saving
    if not hasattr(cleaned_ds, "file_meta") or cleaned_ds.file_meta is None:
        cleaned_ds.file_meta = FileMetaDataset()
    if "TransferSyntaxUID" not in cleaned_ds.file_meta:
        cleaned_ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    if "MediaStorageSOPClassUID" not in cleaned_ds.file_meta:
        cleaned_ds.file_meta.MediaStorageSOPClassUID = getattr(cleaned_ds, "SOPClassUID", "1.2.840.10008.5.1.4.1.1.1")
    if "MediaStorageSOPInstanceUID" not in cleaned_ds.file_meta:
        cleaned_ds.file_meta.MediaStorageSOPInstanceUID = cleaned_ds.SOPInstanceUID

    # Serialize sanitized dataset
    sanitized_bio = io.BytesIO()
    pydicom.dcmwrite(sanitized_bio, cleaned_ds)
    sanitized_bytes = sanitized_bio.getvalue()
    
    # 3. AES-256-GCM Envelope Encryption
    kms = kms or _shared_kms
    plaintext_dek, ciphertext_dek = kms.generate_data_key(settings.kms_master_key_id)
    
    encrypted_container = encrypt_envelope(
        payload=sanitized_bytes,
        plaintext_dek=plaintext_dek,
        kek_id=settings.kms_master_key_id,
        ciphertext_dek=ciphertext_dek
    )
    
    # 4. Save to Encrypted Storage
    if store is None:
        if settings.storage_path not in _shared_store:
            _shared_store[settings.storage_path] = EncryptedStore(storage_dir=settings.storage_path)
        store = _shared_store[settings.storage_path]
        
    saved_path = store.save(anon_study_uid, encrypted_container)
    
    # Audit Log
    audit_logger.info(
        "DICOM_STUDY_INGESTED",
        extra={
            "audit_data": {
                "event_type": "DICOM_INGESTION_AND_ENCRYPTION",
                "anonymous_study_instance_uid": anon_study_uid,
                "burned_in_text_redacted": was_redacted,
                "storage_path": saved_path
            }
        }
    )
    
    return IngestionResponse(
        status="INGESTED_AND_ENCRYPTED",
        anonymous_study_instance_uid=anon_study_uid,
        instances_processed=1,
        burned_in_text_redacted=was_redacted,
        encryption_algorithm="AES-256-GCM",
        storage_object_id=f"studies/{anon_study_uid}.enc",
        timestamp_utc=datetime.now(timezone.utc).isoformat()
    )

@router.post("", response_model=IngestionResponse, status_code=status.HTTP_201_CREATED)
async def upload_study(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
):
    try:
        contents = await file.read()
        return process_and_encrypt_study(contents, settings)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        audit_logger.error(f"Internal ingestion failure: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during study ingestion and encryption.")
