import io
from typing import Any, Dict
import pydicom
from fastapi import APIRouter, Depends, HTTPException, Response, status

from medshield.config import Settings, get_settings
from medshield.crypto.envelope import decrypt_envelope
from medshield.crypto.kms_provider import KMSProvider
from medshield.storage.encrypted_store import EncryptedStore
from medshield.ml.inference_engine import InferenceEngine
from medshield.utils.logging import get_audit_logger

router = APIRouter(prefix="/api/v1", tags=["Inference & Diagnostics"])
audit_logger = get_audit_logger("medshield.audit.inference")

_shared_engine = InferenceEngine()

def process_study_inference(
    study_uid: str,
    settings: Settings,
    kms: KMSProvider = None,
    store: EncryptedStore = None,
    engine: InferenceEngine = None
) -> Dict[str, Any]:
    """
    Core synchronous inference service:
    Loads encrypted container -> Decrypts DEK & DICOM in RAM -> Runs ConvNeXt/EfficientNet ->
    Returns multi-label predictions and triage urgency.
    """
    from medshield.api.routes.studies import _shared_kms, _shared_store
    store = store or _shared_store.get(settings.storage_path) or EncryptedStore(storage_dir=settings.storage_path)
    kms = kms or _shared_kms
    engine = engine or _shared_engine
    
    encrypted_bytes = store.load(study_uid)
    if not encrypted_bytes:
        raise KeyError(f"Study with UID '{study_uid}' not found in encrypted storage")
        
    # Decrypt in memory
    try:
        plaintext_bytes = decrypt_envelope(encrypted_bytes, kms)
    except Exception as e:
        audit_logger.error(f"Decryption failed for study {study_uid}: {str(e)}")
        raise PermissionError(f"Cryptographic decryption failed or key revoked: {str(e)}")
        
    ds = pydicom.dcmread(io.BytesIO(plaintext_bytes), force=True)
    result = engine.predict(ds)
    
    audit_logger.info(
        "STUDY_INFERENCE_EXECUTED",
        extra={
            "audit_data": {
                "event_type": "MODEL_INFERENCE_DECRYPT",
                "anonymous_study_instance_uid": study_uid,
                "latency_ms": result["inference_latency_ms"]
            }
        }
    )
    return result

def generate_study_heatmap(
    study_uid: str,
    pathology: str,
    settings: Settings,
    kms: KMSProvider = None,
    store: EncryptedStore = None,
    engine: InferenceEngine = None
) -> bytes:
    """
    Core synchronous heatmap service:
    Decrypts study in RAM -> Computes Grad-CAM activations -> Returns PNG bytes.
    """
    from medshield.api.routes.studies import _shared_kms, _shared_store
    store = store or _shared_store.get(settings.storage_path) or EncryptedStore(storage_dir=settings.storage_path)
    kms = kms or _shared_kms
    engine = engine or _shared_engine
    
    encrypted_bytes = store.load(study_uid)
    if not encrypted_bytes:
        raise KeyError(f"Study with UID '{study_uid}' not found")
        
    plaintext_bytes = decrypt_envelope(encrypted_bytes, kms)
    ds = pydicom.dcmread(io.BytesIO(plaintext_bytes), force=True)
    
    heatmap_pil = engine.generate_heatmap_image(ds, pathology)
    bio = io.BytesIO()
    heatmap_pil.save(bio, format="PNG")
    return bio.getvalue()

@router.post("/inference/{study_uid}")
async def run_inference(
    study_uid: str,
    settings: Settings = Depends(get_settings)
):
    try:
        return process_study_inference(study_uid, settings)
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ke))
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/heatmaps/{study_uid}/{pathology}")
async def get_heatmap(
    study_uid: str,
    pathology: str,
    settings: Settings = Depends(get_settings)
):
    try:
        img_bytes = generate_study_heatmap(study_uid, pathology, settings)
        return Response(content=img_bytes, media_type="image/png")
    except KeyError:
        raise HTTPException(status_code=404, detail="Study not found")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
