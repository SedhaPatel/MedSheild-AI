from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from medshield.config import Settings, get_settings

class MTLSAuthMiddleware(BaseHTTPMiddleware):
    """
    Enforces Mutual TLS (mTLS) client certificate verification for Zero-Trust edge communication.
    In cloud ingress topology (Envoy / AWS ALB), the edge proxy terminates mTLS and forwards the
    verified client certificate thumbprint in the 'X-Client-Cert-SHA256' header.
    """
    def __init__(self, app, settings: Optional[Settings] = None):
        super().__init__(app)
        self.settings = settings or get_settings()

    async def dispatch(self, request: Request, call_next):
        # Exclude OpenAPI documentation, health checks, clinical dashboard, and scan chat assistant
        if request.url.path in ("/docs", "/openapi.json", "/health", "/", "/dashboard", "/api/chat") or request.url.path.startswith("/api/v1/dashboard"):
            return await call_next(request)

        # Allow public SPA static assets and client-side routes when unified frontend serving is enabled
        if self.settings.serve_frontend_dist and request.method in ("GET", "HEAD") and not request.url.path.startswith("/api"):
            return await call_next(request)

        if self.settings.require_mtls:
            cert_fingerprint = request.headers.get("X-Client-Cert-SHA256")
            if not cert_fingerprint:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Client certificate required: Missing X-Client-Cert-SHA256 header"}
                )
                
            if cert_fingerprint not in self.settings.allowed_client_cert_fingerprints:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Unauthorized client certificate fingerprint"}
                )

        return await call_next(request)

