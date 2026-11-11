import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

class JSONAuditFormatter(logging.Formatter):
    """
    Structured JSON log formatter conforming to HIPAA §164.312(b) audit controls
    and India CERT-In 180-day security log mandates.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Merge audit metadata if provided
        audit_data = getattr(record, "audit_data", None)
        if audit_data and isinstance(audit_data, dict):
            log_entry["audit"] = audit_data
            
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry)

def configure_logging(log_level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Avoid duplicate handlers
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONAuditFormatter())
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(JSONAuditFormatter())

def get_audit_logger(name: str = "medshield.audit") -> logging.Logger:
    return logging.getLogger(name)

