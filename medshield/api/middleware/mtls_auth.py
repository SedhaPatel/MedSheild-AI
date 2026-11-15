from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from medshield.config import Settings, get_settings


class MTLSAuthMiddleware(BaseHTTPMiddleware):
    """
    Enforces Mutual TLS (mTLS) transport perimeter verification when enabled.
    In secure edge ingress topologies, the reverse proxy terminates mTLS, validates
    the client certificate against a trusted PKI CA, and passes the certificate
    fingerprint via 'X-Client-Cert-SHA256'.

    SECURITY CONTROLS:
    1. Only genuinely public endpoints (/health, /api/v1/auth/login, static SPA) bypass mTLS.
    2. Client-supplied headers are NOT trusted unless verified by a trusted reverse proxy
       authenticated via MEDSHIELD_TRUSTED_PROXY_SECRET.
    3. Mock or empty-string fingerprints are strictly rejected.
    4. mTLS transport validation does NOT replace application user JWT authentication.
    """
    def __init__(self, app, settings: Optional[Settings] = None):
        super().__init__(app)
        self.settings = settings or get_settings()

    async def dispatch(self, request: Request, call_next):
        # Exclude genuinely public endpoints: health check, login, and OpenAPI docs (if debug/dev)
        path = request.url.path
        if path in ("/health", "/api/v1/auth/login", "/api/v1/auth/options"):
            return await call_next(request)

        if self.settings.debug and path in ("/docs", "/openapi.json"):
            return await call_next(request)

        # Allow public SPA static assets and client-side routes when unified frontend serving is enabled
        if self.settings.serve_frontend_dist and request.method in ("GET", "HEAD") and not path.startswith("/api"):
            return await call_next(request)

        if self.settings.require_mtls:
            # If trusted_proxy_secret is configured, verify the request originates from the trusted ingress proxy
            if self.settings.trusted_proxy_secret:
                proxy_secret = request.headers.get("X-Proxy-Secret")
                if not proxy_secret or proxy_secret != self.settings.trusted_proxy_secret:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Untrusted ingress: Missing or invalid proxy authentication secret"}
                    )

            cert_fingerprint = request.headers.get("X-Client-Cert-SHA256")
            if not cert_fingerprint:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Client certificate required: Missing X-Client-Cert-SHA256 header"}
                )

            norm_fp = cert_fingerprint.strip().lower()
            allowed = [fp.lower() for fp in self.settings.allowed_client_cert_fingerprints]
            if not allowed or norm_fp not in allowed:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Unauthorized client certificate fingerprint"}
                )

        return await call_next(request)
