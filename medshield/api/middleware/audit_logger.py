import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from medshield.utils.logging import get_audit_logger

class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Emits structured JSON audit trails compliant with HIPAA §164.312(b)
    and India CERT-In 6-hour incident analysis and 180-day retention rules.
    """
    def __init__(self, app):
        super().__init__(app)
        self.logger = get_audit_logger("medshield.api.audit")

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        cert_fingerprint = request.headers.get("X-Client-Cert-SHA256", "none")
        
        response = await call_next(request)
        
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        
        self.logger.info(
            f"{request.method} {request.url.path} -> {response.status_code}",
            extra={
                "audit_data": {
                    "event_type": "HTTP_REQUEST",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "client_ip": client_ip,
                    "cert_fingerprint": cert_fingerprint,
                    "duration_ms": duration_ms
                }
            }
        )
        return response
