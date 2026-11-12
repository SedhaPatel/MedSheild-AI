import os
from functools import lru_cache
from typing import List, Optional
from pydantic import BaseModel, Field

class Settings(BaseModel):
    app_name: str = "MedShield-AI"
    environment: str = os.getenv("MEDSHIELD_ENVIRONMENT", "development")
    debug: bool = os.getenv("MEDSHIELD_DEBUG", "false").lower() in ("true", "1", "yes")
    
    # Storage settings
    storage_backend: str = os.getenv("MEDSHIELD_STORAGE_BACKEND", "local")
    storage_path: str = os.getenv("MEDSHIELD_STORAGE_PATH", "./storage/encrypted_studies")
    
    # Cryptographic settings
    secret_pepper: bytes = Field(
        default=os.getenv("MEDSHIELD_SECRET_PEPPER", "MedShieldDefaultMasterSalt2026-StrictSec!").encode("utf-8"),
        description="Master salt for salted HMAC-SHA256 UID pseudonymization"
    )
    kms_master_key_id: str = os.getenv("MEDSHIELD_KMS_MASTER_KEY_ID", "arn:medshield:kms:local:key/master-kek-v1")
    
    # Network and security settings
    tls_min_version: str = os.getenv("MEDSHIELD_TLS_MIN_VERSION", "TLSv1.3")
    require_mtls: bool = os.getenv("MEDSHIELD_REQUIRE_MTLS", "true").lower() in ("true", "1", "yes")
    allowed_client_cert_fingerprints: List[str] = Field(
        default_factory=lambda: [
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "mock-edge-gateway-cert-fingerprint-valid"
        ]
    )
    
    # Model inference settings
    model_architecture: str = os.getenv("MEDSHIELD_MODEL_ARCHITECTURE", "efficientnet_v2_s")
    model_checkpoint_path: Optional[str] = os.getenv("MEDSHIELD_MODEL_CHECKPOINT_PATH", None)
    target_pathologies: List[str] = Field(
        default_factory=lambda: [
            "Pneumonia",
            "Cardiomegaly",
            "Pleural Effusion",
            "Pneumothorax",
            "Atelectasis"
        ]
    )

    # Chat VLM assistant settings
    chat_provider: str = Field(default_factory=lambda: os.getenv("MEDSHIELD_CHAT_PROVIDER", "gemini"))
    gemini_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", None))
    gemini_model: str = Field(default_factory=lambda: os.getenv("MEDSHIELD_GEMINI_MODEL", "gemini-2.5-flash"))
    hf_api_token: Optional[str] = Field(default_factory=lambda: os.getenv("HF_API_TOKEN", None))
    medgemma_model: str = Field(default_factory=lambda: os.getenv("MEDSHIELD_MEDGEMMA_MODEL", "google/medgemma-1.5-4b-it"))
    chat_timeout_sec: float = Field(default_factory=lambda: float(os.getenv("MEDSHIELD_CHAT_TIMEOUT_SEC", "25.0")))

    def model_post_init(self, __context) -> None:
        super().model_post_init(__context)
        # Defense-in-depth: enforce non-default salt in production
        if self.environment.lower() == "production":
            if self.secret_pepper == b"MedShieldDefaultMasterSalt2026-StrictSec!":
                raise ValueError("MEDSHIELD_SECRET_PEPPER must be explicitly set to a unique secret in production!")

@lru_cache()
def get_settings() -> Settings:
    return Settings()
