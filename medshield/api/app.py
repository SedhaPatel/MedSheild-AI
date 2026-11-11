from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from medshield.config import Settings, get_settings
from medshield.api.middleware.mtls_auth import MTLSAuthMiddleware
from medshield.api.middleware.audit_logger import AuditLoggingMiddleware
from medshield.api.routes.studies import router as studies_router
from medshield.api.routes.inference import router as inference_router
from medshield.utils.logging import configure_logging

def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(log_level="INFO")
    
    app = FastAPI(
        title="MedShield-AI Ingestion and Inference API",
        description="HIPAA and India DPDP-compliant zero-trust DICOM ingestion, AES-256-GCM storage, and disease detection platform.",
        version="0.1.0"
    )
    
    # Register Middlewares (Order: AuditLogger wraps MTLSAuth wraps Handlers)
    app.add_middleware(AuditLoggingMiddleware)
    app.add_middleware(MTLSAuthMiddleware, settings=settings)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register API Routers
    app.include_router(studies_router)
    app.include_router(inference_router)
    
    @app.get("/health", tags=["Health"])
    def health_check():
        return {
            "status": "HEALTHY",
            "app_name": settings.app_name,
            "security": {
                "tls_enforced": settings.tls_min_version,
                "mtls_required": settings.require_mtls,
                "encryption": "AES-256-GCM Envelope"
            }
        }
        
    return app

app = create_app()
