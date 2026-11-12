import json
import os
from functools import lru_cache
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator

DEFAULT_SECRET_PEPPER = "MedShieldDefaultMasterSalt2026-StrictSec!"

DEFAULT_CORS_ORIGINS: List[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "yes")


def _parse_cors_origins(raw: Optional[str]) -> List[str]:
    if raw is None or not raw.strip():
        return list(DEFAULT_CORS_ORIGINS)

    stripped = raw.strip()
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [
                    str(item).strip().rstrip("/")
                    for item in parsed
                    if str(item).strip()
                ]
        except json.JSONDecodeError:
            pass

    return [
        origin.strip().rstrip("/")
        for origin in stripped.split(",")
        if origin.strip()
    ]


class Settings(BaseModel):
    app_name: str = "MedShield-AI"
    environment: str = Field(default_factory=lambda: os.getenv("MEDSHIELD_ENVIRONMENT", "development"))
    debug: bool = Field(default_factory=lambda: _parse_bool_env("MEDSHIELD_DEBUG", False))

    # Storage settings
    storage_backend: str = Field(default_factory=lambda: os.getenv("MEDSHIELD_STORAGE_BACKEND", "local"))
    storage_path: str = Field(default_factory=lambda: os.getenv("MEDSHIELD_STORAGE_PATH", "./storage/encrypted_studies"))

    # Cryptographic settings
    secret_pepper: bytes = Field(
        default_factory=lambda: os.getenv("MEDSHIELD_SECRET_PEPPER", DEFAULT_SECRET_PEPPER).encode("utf-8"),
        description="Master salt for salted HMAC-SHA256 UID pseudonymization"
    )
    kms_master_key_id: str = Field(
        default_factory=lambda: os.getenv("MEDSHIELD_KMS_MASTER_KEY_ID", "arn:medshield:kms:local:key/master-kek-v1")
    )
    # Optional file that persists LocalKMSProvider keys across restarts (unset = in-memory only)
    kms_keystore_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("MEDSHIELD_KMS_KEYSTORE_PATH") or None
    )

    # Network and security settings
    tls_min_version: str = Field(default_factory=lambda: os.getenv("MEDSHIELD_TLS_MIN_VERSION", "TLSv1.3"))
    require_mtls: bool = Field(default_factory=lambda: _parse_bool_env("MEDSHIELD_REQUIRE_MTLS", True))
    allowed_client_cert_fingerprints: List[str] = Field(
        default_factory=lambda: [
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "mock-edge-gateway-cert-fingerprint-valid"
        ]
    )
    cors_origins: List[str] = Field(
        default_factory=lambda: _parse_cors_origins(os.getenv("MEDSHIELD_CORS_ORIGINS"))
    )

    # Maximum accepted upload size (DICOM / PNG / JPEG) in megabytes
    max_upload_mb: float = Field(default_factory=lambda: float(os.getenv("MEDSHIELD_MAX_UPLOAD_MB", "100")))

    # Optional unified SPA static hosting settings
    serve_frontend_dist: bool = Field(default_factory=lambda: _parse_bool_env("MEDSHIELD_SERVE_FRONTEND", False))
    frontend_dist_dir: str = Field(
        default_factory=lambda: os.getenv("MEDSHIELD_FRONTEND_DIST_DIR", "./frontend/dist")
    )

    # Model inference settings
    model_architecture: str = Field(
        default_factory=lambda: os.getenv("MEDSHIELD_MODEL_ARCHITECTURE", "torchxrayvision")
    )
    model_checkpoint_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("MEDSHIELD_MODEL_CHECKPOINT_PATH") or None
    )
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
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("MEDSHIELD_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    )
    ollama_model: str = Field(
        default_factory=lambda: os.getenv("MEDSHIELD_OLLAMA_MODEL", "llama3.2-vision")
    )
    chat_timeout_sec: float = Field(default_factory=lambda: float(os.getenv("MEDSHIELD_CHAT_TIMEOUT_SEC", "25.0")))

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _validate_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _parse_cors_origins(value)
        if isinstance(value, (list, tuple)):
            return [str(item).strip().rstrip("/") for item in value if str(item).strip()]
        return value

    def model_post_init(self, __context) -> None:
        super().model_post_init(__context)
        # Defense-in-depth: enforce non-default salt in production
        if self.environment.lower() == "production":
            if not self.secret_pepper or self.secret_pepper == DEFAULT_SECRET_PEPPER.encode("utf-8"):
                raise ValueError("MEDSHIELD_SECRET_PEPPER must be explicitly set to a unique secret in production!")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
