import asyncio
import base64
import io
import numpy as np
import pytest
from PIL import Image
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from medshield.config import Settings
from medshield.ml.chat_service import (
    redact_chat_pii,
    build_grounded_system_prompt,
    assert_zero_pii_and_extract_image,
    ScanChatService,
    compute_heatmap_zone_summary,
)


def make_compliant_dicom(burned_in: str = "NO") -> Dataset:
    """Creates a synthetic DICOM dataset compliant with HIPAA Safe Harbor."""
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1"
    file_meta.MediaStorageSOPInstanceUID = "2.25.10000000001"

    ds = Dataset()
    ds.file_meta = file_meta
    ds.PatientIdentityRemoved = "YES"
    ds.BurnedInAnnotation = burned_in
    ds.PatientID = "ANON_98765432"
    ds.StudyInstanceUID = "2.25.10000000002"
    ds.SeriesInstanceUID = "2.25.10000000003"
    ds.SOPInstanceUID = "2.25.10000000001"
    ds.Modality = "DX"
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows = 128
    ds.Columns = 128
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1

    arr = np.full((128, 128), 1000, dtype=np.uint16)
    arr[40:88, 40:88] = 3000
    ds.PixelData = arr.tobytes()
    return ds


def test_redact_chat_pii_masks_mrn_dob_phone_email():
    raw = "Patient DOB 1982-04-19 MRN-88412 phone 555-234-8910 email jane@hosp.org shows opacity."
    cleaned, redacted = redact_chat_pii(raw)
    assert redacted is True
    assert "1982-04-19" not in cleaned
    assert "MRN-88412" not in cleaned
    assert "555-234-8910" not in cleaned
    assert "jane@hosp.org" not in cleaned
    assert "[REDACTED_PII]" in cleaned


def test_redact_chat_pii_leaves_clean_text_intact():
    raw = "The radiograph demonstrates clear bilateral costophrenic angles with no evidence of effusion."
    cleaned, redacted = redact_chat_pii(raw)
    assert redacted is False
    assert cleaned == raw


def test_grounded_system_prompt_contains_only_model_metrics_and_disclaimer():
    prompt = build_grounded_system_prompt(
        predictions=[{"pathology": "Pneumonia", "probability": 0.72, "epistemic_uncertainty": 0.031, "triage_urgency": "STAT_CRITICAL"}],
        target_pathology="Pneumonia",
    )
    assert "Pneumonia" in prompt
    assert "72.0%" in prompt
    assert "diagnosis" in prompt.lower()


def test_assert_zero_pii_and_extract_image_success_on_compliant_dataset():
    ds = make_compliant_dicom(burned_in="NO")
    b64_img = assert_zero_pii_and_extract_image(ds)
    assert isinstance(b64_img, str)
    assert len(b64_img) > 100

    raw_bytes = base64.b64decode(b64_img)
    pil_img = Image.open(io.BytesIO(raw_bytes))
    assert pil_img.format == "PNG"
    assert pil_img.mode == "RGB"
    assert pil_img.width <= 768
    assert pil_img.height <= 768


def test_assert_zero_pii_and_extract_image_rejects_non_compliant_dataset():
    ds = make_compliant_dicom(burned_in="NO")
    ds.PatientName = "DOE^JOHN"
    with pytest.raises(ValueError, match="violates HIPAA/Safe Harbor"):
        assert_zero_pii_and_extract_image(ds)


def test_assert_zero_pii_and_extract_image_rejects_burned_in_annotation():
    ds = make_compliant_dicom(burned_in="YES")
    with pytest.raises(ValueError, match="BurnedInAnnotation"):
        assert_zero_pii_and_extract_image(ds)


def test_compute_heatmap_zone_summary():
    img = Image.new("RGB", (300, 300), color=(10, 10, 10))
    # Place bright spot in bottom left (viewer-left, lower zone)
    for y in range(220, 280):
        for x in range(20, 80):
            img.putpixel((x, y), (255, 30, 30))

    summary = compute_heatmap_zone_summary(img)
    assert "Lower" in summary or "Basilar" in summary or "viewer-left" in summary.lower() or "right" in summary.lower()


def test_chat_service_offline_fallback_when_credentials_unset(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("HF_API_TOKEN", "")

    ds = make_compliant_dicom(burned_in="NO")
    predictions = [
        {"pathology": "Pneumonia", "probability": 0.8123, "epistemic_uncertainty": 0.0211, "triage_urgency": "STAT_CRITICAL"},
        {"pathology": "Cardiomegaly", "probability": 0.1200, "epistemic_uncertainty": 0.0150, "triage_urgency": "ROUTINE"},
    ]

    service = ScanChatService()
    reply = asyncio.run(service.generate_reply(
        dataset=ds,
        user_message="Explain what the AI found.",
        predictions=predictions,
        target_pathology="Pneumonia",
        conversation_history=[],
    ))

    assert reply["provider_used"] == "grounded-local-fallback"
    assert "Pneumonia" in reply["answer"]
    assert reply["zero_pii_verified"] is True
    assert reply["pii_redacted_from_prompt"] is False
    assert len(reply["grounded_findings"]) == 2
    assert "diagnosis" in reply["medical_disclaimer"].lower()


def test_chat_service_gemini_transport_payload_zero_phi(monkeypatch):
    monkeypatch.setenv("MEDSHIELD_CHAT_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-test-key-123")

    captured_requests = []

    import httpx

    async def mock_post(self, url, **kwargs):
        captured_requests.append({"url": str(url), **kwargs})
        mock_response = httpx.Response(
            status_code=200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "The scan shows consolidation in the right lung field."}]
                        }
                    }
                ]
            },
            request=httpx.Request("POST", str(url)),
        )
        return mock_response

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    ds = make_compliant_dicom(burned_in="NO")
    predictions = [
        {"pathology": "Pneumonia", "probability": 0.85, "epistemic_uncertainty": 0.02, "triage_urgency": "STAT_CRITICAL"}
    ]

    service = ScanChatService()
    reply = asyncio.run(service.generate_reply(
        dataset=ds,
        user_message="Patient DOB 1990-01-01 MRN-998811 opacity query",
        predictions=predictions,
        target_pathology="Pneumonia",
        conversation_history=[{"role": "user", "content": "Hello"}],
    ))

    assert reply["provider_used"] == "gemini-2.5-flash"
    assert reply["pii_redacted_from_prompt"] is True
    assert reply["zero_pii_verified"] is True
    assert "consolidation" in reply["answer"]

    # Verify captured outbound payload contains NO raw PII
    assert len(captured_requests) == 1
    req = captured_requests[0]
    json_body = req.get("json", {})
    body_str = str(json_body)
    assert "1990-01-01" not in body_str
    assert "MRN-998811" not in body_str
    assert "[REDACTED_PII]" in body_str
    # Check that image parts are present and valid base64
    assert "inlineData" in body_str or "inline_data" in body_str


def test_chat_service_medgemma_transport_payload_zero_phi(monkeypatch):
    monkeypatch.setenv("MEDSHIELD_CHAT_PROVIDER", "medgemma")
    monkeypatch.setenv("HF_API_TOKEN", "mock-hf-test-token-456")

    captured_requests = []

    import httpx

    async def mock_post(self, url, **kwargs):
        captured_requests.append({"url": str(url), **kwargs})
        mock_response = httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "MedGemma analysis indicates localized opacity.",
                        }
                    }
                ]
            },
            request=httpx.Request("POST", str(url)),
        )
        return mock_response

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    ds = make_compliant_dicom(burned_in="NO")
    predictions = [
        {"pathology": "Pneumonia", "probability": 0.85, "epistemic_uncertainty": 0.02, "triage_urgency": "STAT_CRITICAL"}
    ]

    service = ScanChatService()
    reply = asyncio.run(service.generate_reply(
        dataset=ds,
        user_message="What did the model observe?",
        predictions=predictions,
        target_pathology="Pneumonia",
        conversation_history=[],
    ))

    assert reply["provider_used"] == "google/medgemma-1.5-4b-it"
    assert reply["zero_pii_verified"] is True
    assert "MedGemma analysis" in reply["answer"]

    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert "router.huggingface.co" in req["url"]
    assert "Bearer mock-hf-test-token-456" in req["headers"]["Authorization"]


def test_config_chat_settings_default_and_env_override(monkeypatch):
    monkeypatch.setenv("MEDSHIELD_CHAT_PROVIDER", "medgemma")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("MEDSHIELD_GEMINI_MODEL", "gemini-test-custom")
    monkeypatch.setenv("HF_API_TOKEN", "test-token")
    monkeypatch.setenv("MEDSHIELD_MEDGEMMA_MODEL", "custom/medgemma")
    monkeypatch.setenv("MEDSHIELD_CHAT_TIMEOUT_SEC", "35.5")

    settings = Settings()
    assert settings.chat_provider == "medgemma"
    assert settings.gemini_api_key == "test-key"
    assert settings.gemini_model == "gemini-test-custom"
    assert settings.hf_api_token == "test-token"
    assert settings.medgemma_model == "custom/medgemma"
    assert settings.chat_timeout_sec == 35.5


def test_chat_service_gemini_with_heatmap_overlay(monkeypatch):
    monkeypatch.setenv("MEDSHIELD_CHAT_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-test-key-123")

    captured_requests = []
    import httpx

    async def mock_post(self, url, **kwargs):
        captured_requests.append({"url": str(url), **kwargs})
        return httpx.Response(
            status_code=200,
            json={"candidates": [{"content": {"parts": [{"text": "Heatmap localized in right lower lobe."}]}}]},
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    ds = make_compliant_dicom(burned_in="NO")
    predictions = [
        {"pathology": "Pneumonia", "probability": 0.88, "epistemic_uncertainty": 0.015, "triage_urgency": "STAT_CRITICAL"}
    ]
    heatmap_pil = Image.new("RGB", (256, 256), color=(20, 20, 20))

    service = ScanChatService()
    reply = asyncio.run(service.generate_reply(
        dataset=ds,
        user_message="Where is the consolidation?",
        predictions=predictions,
        target_pathology="Pneumonia",
        conversation_history=[],
        heatmap_pil=heatmap_pil,
    ))

    assert reply["provider_used"] == "gemini-2.5-flash"
    assert len(captured_requests) == 1
    req_body = captured_requests[0].get("json", {})
    # System instruction must mention Grad-CAM
    sys_text = req_body["systemInstruction"]["parts"][0]["text"]
    assert "Grad-CAM Heatmap Localization" in sys_text
    # User parts must contain two image parts: scan + heatmap
    user_parts = req_body["contents"][0]["parts"]
    image_parts = [p for p in user_parts if "inlineData" in p]
    assert len(image_parts) == 2


def test_chat_service_prunes_conversation_history_to_last_six_turns(monkeypatch):
    monkeypatch.setenv("MEDSHIELD_CHAT_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-test-key-123")

    captured_requests = []
    import httpx

    async def mock_post(self, url, **kwargs):
        captured_requests.append({"url": str(url), **kwargs})
        return httpx.Response(
            status_code=200,
            json={"candidates": [{"content": {"parts": [{"text": "History check passed."}]}}]},
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    ds = make_compliant_dicom(burned_in="NO")
    history = [{"role": "user" if i % 2 == 0 else "model", "content": f"Turn {i}"} for i in range(12)]

    service = ScanChatService()
    reply = asyncio.run(service.generate_reply(
        dataset=ds,
        user_message="Latest turn",
        predictions=[{"pathology": "Pneumonia", "probability": 0.70, "epistemic_uncertainty": 0.02, "triage_urgency": "STAT_CRITICAL"}],
        target_pathology="Pneumonia",
        conversation_history=history,
    ))

    assert reply["provider_used"] == "gemini-2.5-flash"
    req_body = captured_requests[0].get("json", {})
    # 6 history turns + 1 current user turn = 7 turns total in contents
    contents = req_body["contents"]
    assert len(contents) == 7
    # First history turn sent should be Turn 6 (since range 12 has 0..11, last 6 are 6..11)
    assert contents[0]["parts"][0]["text"] == "Turn 6"


def test_chat_service_upstream_http_error_falls_back_to_offline(monkeypatch):
    monkeypatch.setenv("MEDSHIELD_CHAT_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-test-key-123")

    import httpx

    async def mock_post_500(self, url, **kwargs):
        return httpx.Response(
            status_code=500,
            json={"error": "Google Gemini Internal Server Error"},
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_500)

    ds = make_compliant_dicom(burned_in="NO")
    predictions = [
        {"pathology": "Pneumothorax", "probability": 0.92, "epistemic_uncertainty": 0.01, "triage_urgency": "STAT_CRITICAL"}
    ]

    service = ScanChatService()
    reply = asyncio.run(service.generate_reply(
        dataset=ds,
        user_message="Is there tension pneumothorax?",
        predictions=predictions,
        target_pathology="Pneumothorax",
        conversation_history=[],
    ))

    # Gracefully falls back to deterministic local reply
    assert reply["provider_used"] == "grounded-local-fallback"
    assert "Pneumothorax" in reply["answer"]
    assert "92.0%" in reply["answer"]
    assert reply["zero_pii_verified"] is True


from fastapi.testclient import TestClient
from medshield.api.app import create_app
from medshield.config import get_settings
from medshield.api.routes.dashboard import _dashboard_session_cache, _dashboard_kms


def test_chat_endpoint_rejects_shredded_study_with_410_and_never_leaks_phi(monkeypatch, tmp_path):
    storage_dir = str(tmp_path / "enc_studies")
    settings = Settings(
        storage_path=storage_dir,
        secret_pepper=b"test-salt-shred-1",
        require_mtls=True,
        chat_provider="gemini",
        gemini_api_key="mock-gemini-key",
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)

    # 1. Analyze patient_01_pneumonia via /api/v1/dashboard/analyze -> capture anonymous_study_instance_uid
    analyze_resp = client.post(
        "/api/v1/dashboard/analyze",
        data={"sample_id": "patient_01_pneumonia", "pathology_heatmap": "Pneumonia"},
    )
    assert analyze_resp.status_code == 200, analyze_resp.text
    analysis_data = analyze_resp.json()
    uid = analysis_data["anonymous_study_instance_uid"]

    # Verify pre-sanitization PII is stored in _dashboard_session_cache
    assert uid in _dashboard_session_cache
    cached_pre_pii = _dashboard_session_cache[uid]["pre_pii_tags"]
    raw_name = cached_pre_pii.get("PatientName", "")
    raw_id = cached_pre_pii.get("PatientID", "")
    assert len(raw_name) > 0
    assert len(raw_id) > 0

    # 2. Mock httpx.AsyncClient.post to capture exact outbound text + image args
    captured_requests = []
    import httpx

    async def mock_post(self, url, **kwargs):
        captured_requests.append({"url": str(url), **kwargs})
        return httpx.Response(
            status_code=200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Visual analysis confirms localized consolidation."}]
                        }
                    }
                ]
            },
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    # 3. Call POST /api/chat with {"scan_id": uid, "user_message": "What did the heatmap highlight?", "include_heatmap_overlay": True}
    chat_resp = client.post(
        "/api/chat",
        json={
            "scan_id": uid,
            "user_message": "What did the heatmap highlight?",
            "include_heatmap_overlay": True,
            "conversation_history": [
                {"role": "user", "content": "Initial inquiry"},
                {"role": "assistant", "content": "Prior reply"}
            ],
        },
    )

    # 4. Assert 200 OK, zero_pii_verified is True, captured outbound payload has NO pre-sanitization PatientName/PatientID
    assert chat_resp.status_code == 200, chat_resp.text
    chat_data = chat_resp.json()
    assert chat_data["scan_id"] == uid
    assert chat_data["zero_pii_verified"] is True
    assert chat_data["provider_used"] == "gemini-2.5-flash"
    assert "consolidation" in chat_data["answer"]
    assert len(chat_data["grounded_findings"]) > 0
    assert "diagnosis" in chat_data["medical_disclaimer"].lower()

    assert len(captured_requests) == 1
    req_body_str = str(captured_requests[0].get("json", {}))
    assert raw_name not in req_body_str
    assert raw_id not in req_body_str
    # Confirm heatmap overlay was included in outbound parts
    parts = captured_requests[0]["json"]["contents"][-1]["parts"]
    image_parts = [p for p in parts if "inlineData" in p]
    assert len(image_parts) == 2  # scan image + heatmap overlay

    # 5. Call POST /api/v1/dashboard/shred/{uid}
    shred_resp = client.post(f"/api/v1/dashboard/shred/{uid}")
    assert shred_resp.status_code == 200
    assert shred_resp.json()["status"] == "CRYPTO_SHREDDED"

    # 6. Retry POST /api/chat -> assert HTTP 410 Gone
    retry_resp = client.post(
        "/api/chat",
        json={
            "scan_id": uid,
            "user_message": "Can you still read this scan?",
        },
    )
    assert retry_resp.status_code == 410
    assert "revoked" in retry_resp.json()["detail"].lower() or "shredded" in retry_resp.json()["detail"].lower()


def test_chat_endpoint_alias_and_404_handling(tmp_path):
    storage_dir = str(tmp_path / "enc_studies")
    settings = Settings(storage_path=storage_dir, secret_pepper=b"test-salt-alias-2", require_mtls=False)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)

    # Ingest a study
    analyze_resp = client.post(
        "/api/v1/dashboard/analyze",
        data={"sample_id": "patient_01_pneumonia"},
    )
    assert analyze_resp.status_code == 200
    uid = analyze_resp.json()["anonymous_study_instance_uid"]

    # 1. Alias route /api/v1/dashboard/chat works identically
    alias_resp = client.post(
        "/api/v1/dashboard/chat",
        json={
            "scan_id": uid,
            "user_message": "Describe findings",
        },
    )
    assert alias_resp.status_code == 200
    assert alias_resp.json()["scan_id"] == uid
    assert alias_resp.json()["provider_used"] == "grounded-local-fallback"

    # 2. Non-existent scan_id returns 404
    missing_resp = client.post(
        "/api/chat",
        json={
            "scan_id": "2.25.999999999999999999999",
            "user_message": "Is anyone there?",
        },
    )
    assert missing_resp.status_code == 404
    assert "not found" in missing_resp.json()["detail"].lower()


def test_chat_endpoint_mtls_exemption_and_core_protection(tmp_path):
    storage_dir = str(tmp_path / "enc_studies")
    settings = Settings(storage_path=storage_dir, secret_pepper=b"test-salt-mtls-3", require_mtls=True)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)

    # Ingest study (dashboard endpoint is exempted from mTLS)
    analyze_resp = client.post(
        "/api/v1/dashboard/analyze",
        data={"sample_id": "patient_01_pneumonia"},
    )
    assert analyze_resp.status_code == 200
    uid = analyze_resp.json()["anonymous_study_instance_uid"]

    # 1. Core protected routes WITHOUT client cert fail with 401
    core_resp = client.get("/api/v1/studies")
    assert core_resp.status_code == 401
    assert "Client certificate required" in core_resp.json()["error"]

    # 2. POST /api/chat WITHOUT client cert succeeds (exempted)
    chat_resp = client.post(
        "/api/chat",
        json={"scan_id": uid, "user_message": "Evaluate scan"},
    )
    assert chat_resp.status_code == 200
    assert chat_resp.json()["scan_id"] == uid


def test_chat_endpoint_target_pathology_and_fallback(tmp_path):
    storage_dir = str(tmp_path / "enc_studies")
    settings = Settings(storage_path=storage_dir, secret_pepper=b"test-salt-pathology-4", require_mtls=False)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)

    analyze_resp = client.post(
        "/api/v1/dashboard/analyze",
        data={"sample_id": "patient_01_pneumonia"},
    )
    assert analyze_resp.status_code == 200
    uid = analyze_resp.json()["anonymous_study_instance_uid"]

    # Explicit matched pathology
    resp1 = client.post(
        "/api/chat",
        json={"scan_id": uid, "user_message": "Tell me about Cardiomegaly", "target_pathology": "Cardiomegaly"},
    )
    assert resp1.status_code == 200
    assert "Cardiomegaly" in resp1.json()["answer"]

    # Unknown pathology falls back to highest-probability item
    resp2 = client.post(
        "/api/chat",
        json={"scan_id": uid, "user_message": "Tell me about condition X", "target_pathology": "NonExistentPathology"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["zero_pii_verified"] is True


def test_chat_endpoint_zero_pii_violation_returns_422(monkeypatch, tmp_path):
    storage_dir = str(tmp_path / "enc_studies")
    settings = Settings(storage_path=storage_dir, secret_pepper=b"test-salt-422-5", require_mtls=False)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)

    analyze_resp = client.post(
        "/api/v1/dashboard/analyze",
        data={"sample_id": "patient_01_pneumonia"},
    )
    assert analyze_resp.status_code == 200
    uid = analyze_resp.json()["anonymous_study_instance_uid"]

    async def mock_generate_reply(*args, **kwargs):
        raise ValueError("DICOM dataset violates HIPAA/Safe Harbor zero-PII compliance: PatientName retained")

    monkeypatch.setattr(ScanChatService, "generate_reply", mock_generate_reply)

    resp = client.post(
        "/api/chat",
        json={"scan_id": uid, "user_message": "Tell me about this scan"},
    )
    assert resp.status_code == 422
    assert "violates HIPAA/Safe Harbor" in resp.json()["detail"]


