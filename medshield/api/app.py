import mimetypes
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from medshield.config import Settings, get_settings
from medshield.api.middleware.mtls_auth import MTLSAuthMiddleware
from medshield.api.middleware.audit_logger import AuditLoggingMiddleware
from medshield.api.routes.studies import router as studies_router
from medshield.api.routes.inference import router as inference_router
from medshield.api.routes.dashboard import router as dashboard_router
from medshield.utils.logging import configure_logging

mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("application/javascript", ".mjs")


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(log_level="INFO")

    app = FastAPI(
        title="MedShield-AI Ingestion and Inference API",
        description="HIPAA and India DPDP-compliant zero-trust DICOM ingestion, AES-256-GCM storage, and disease detection platform.",
        version="0.1.0"
    )

    allow_origins = settings.cors_origins
    allow_credentials = "*" not in allow_origins

    # Register Middlewares (Order: last added runs outermost -> CORSMiddleware -> MTLSAuth -> AuditLogger -> Handlers)
    app.add_middleware(AuditLoggingMiddleware)
    app.add_middleware(MTLSAuthMiddleware, settings=settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    # Register API Routers
    app.include_router(studies_router)
    app.include_router(inference_router)
    app.include_router(dashboard_router)

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

    dist_dir = Path(settings.frontend_dist_dir).resolve()
    index_file = dist_dir / "index.html"
    serve_spa = bool(settings.serve_frontend_dist and dist_dir.is_dir() and index_file.is_file())

    if serve_spa:
        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        @app.get("/", include_in_schema=False)
        def serve_frontend_root():
            return FileResponse(index_file)

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_frontend_spa(full_path: str):
            # Preserve 404 JSON responses for unknown API routes instead of returning SPA HTML
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")

            candidate = (dist_dir / full_path).resolve()
            try:
                is_within_dist = candidate.is_relative_to(dist_dir)
            except ValueError:
                is_within_dist = False

            if full_path and is_within_dist and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index_file)
    else:
        @app.get("/", tags=["Dashboard"])
        def root_dashboard():
            return RedirectResponse(url="/dashboard")

    return app


app = create_app()
