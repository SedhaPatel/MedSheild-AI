import pytest
from medshield.config import Settings, get_settings
from medshield.utils.logging import configure_logging, get_audit_logger

def test_settings_load_defaults():
    settings = Settings()
    assert settings.app_name == "MedShield-AI"
    assert settings.storage_backend in ["local", "s3"]
    assert len(settings.secret_pepper) >= 16
    assert settings.kms_master_key_id is not None
    assert settings.tls_min_version == "TLSv1.3"

def test_settings_singleton():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

def test_audit_logger_json_format(caplog):
    configure_logging(log_level="INFO")
    logger = get_audit_logger("test.audit")
    
    logger.info(
        "STUDY_INGESTED",
        extra={
            "audit_data": {
                "event_type": "STUDY_INGESTION",
                "patient_pseudonym_uid": "2.25.12345",
                "actor_id": "gateway-edge-01",
                "client_ip": "127.0.0.1"
            }
        }
    )
    
    assert "STUDY_INGESTED" in caplog.text
    assert any(record.getMessage() == "STUDY_INGESTED" for record in caplog.records)
