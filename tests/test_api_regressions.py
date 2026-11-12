"""Regression tests for cross-router KMS sharing, sample_id traversal, and heatmap URL suffixes."""

from fastapi.testclient import TestClient

from medshield.api.app import create_app
from medshield.config import Settings, get_settings

MTLS_HEADER = {"X-Client-Cert-SHA256": "mock-edge-gateway-cert-fingerprint-valid"}


def _client(tmp_path, pepper: bytes = b"regression-tests-unique-pepper") -> TestClient:
    # Unique pepper -> unique anon UIDs, so keys shredded by other tests in the shared KMS don't interfere
    settings = Settings(storage_path=str(tmp_path / "enc"), require_mtls=True, secret_pepper=pepper)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_stow_rs_upload_does_not_break_dashboard_study_with_same_uid(tmp_path):
    client = _client(tmp_path)
    analyzed = client.post("/api/v1/dashboard/analyze", data={"sample_id": "patient_01_pneumonia"})
    assert analyzed.status_code == 200, analyzed.text
    uid = analyzed.json()["anonymous_study_instance_uid"]

    # Same source file via STOW-RS pseudonymizes to the same UID and overwrites the same .enc path
    with open("test_samples/patient_01_pneumonia.dcm", "rb") as f:
        stow = client.post("/api/v1/studies", headers=MTLS_HEADER, files={"file": ("p.dcm", f)})
    assert stow.status_code == 201, stow.text
    assert stow.json()["anonymous_study_instance_uid"] == uid

    # Dashboard must still be able to decrypt it (previously 410 "revoked" due to separate KMS instances)
    resp = client.get(f"/api/v1/dashboard/studies/{uid}/dicom")
    assert resp.status_code == 200, resp.text


def test_analyze_rejects_sample_id_path_traversal(tmp_path):
    client = _client(tmp_path)
    resp = client.post(
        "/api/v1/dashboard/analyze",
        data={"sample_id": "../test_samples/patient_02_effusion"},
    )
    assert resp.status_code == 404


def test_heatmap_url_returned_by_inference_is_fetchable(tmp_path):
    client = _client(tmp_path)
    with open("test_samples/patient_01_pneumonia.dcm", "rb") as f:
        uid = client.post(
            "/api/v1/studies", headers=MTLS_HEADER, files={"file": ("p.dcm", f)}
        ).json()["anonymous_study_instance_uid"]

    inference = client.post(f"/api/v1/inference/{uid}", headers=MTLS_HEADER)
    assert inference.status_code == 200, inference.text
    urls = [p["gradcam_heatmap_url"] for p in inference.json()["predictions"] if p["gradcam_heatmap_url"]]
    assert urls

    resp = client.get(urls[0], headers=MTLS_HEADER)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"


def test_reingesting_shredded_study_returns_409_not_500(tmp_path):
    client = _client(tmp_path, pepper=b"regression-tests-shred-pepper")
    uid = client.post(
        "/api/v1/dashboard/analyze", data={"sample_id": "patient_03_cardiomegaly"}
    ).json()["anonymous_study_instance_uid"]
    assert client.post(f"/api/v1/dashboard/shred/{uid}").status_code == 200

    resp = client.post("/api/v1/dashboard/analyze", data={"sample_id": "patient_03_cardiomegaly"})
    assert resp.status_code == 409, resp.text


def test_lost_key_after_restart_returns_503_not_shredded_410(tmp_path, monkeypatch):
    import medshield.api.routes.dashboard as dashboard
    from medshield.crypto.kms_provider import LocalKMSProvider

    client = _client(tmp_path, pepper=b"regression-tests-restart-pepper")
    uid = client.post(
        "/api/v1/dashboard/analyze", data={"sample_id": "patient_02_effusion"}
    ).json()["anonymous_study_instance_uid"]

    # A fresh in-memory KMS is what the server has after a restart without a keystore
    monkeypatch.setattr(dashboard, "_dashboard_kms", LocalKMSProvider())
    resp = client.get(f"/api/v1/dashboard/studies/{uid}/dicom")
    assert resp.status_code == 503, resp.text
    assert "MEDSHIELD_KMS_KEYSTORE_PATH" in resp.json()["detail"]


def test_oversized_uploads_are_rejected_with_413(tmp_path):
    settings = Settings(storage_path=str(tmp_path / "enc"), require_mtls=False, max_upload_mb=0.001)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    payload = b"\0" * 4096   # > 0.001 MB (~1 KB)

    resp = client.post("/api/v1/dashboard/analyze", files={"file": ("big.dcm", payload)})
    assert resp.status_code == 413, resp.text
    resp = client.post("/api/v1/studies", files={"file": ("big.dcm", payload)})
    assert resp.status_code == 413, resp.text


def test_chat_follow_up_with_long_assistant_history_is_accepted(tmp_path):
    client = _client(tmp_path, pepper=b"regression-tests-chat-history")
    uid = client.post(
        "/api/v1/dashboard/analyze", data={"sample_id": "patient_01_pneumonia"}
    ).json()["anonymous_study_instance_uid"]
    long_answer = "**Plain-Language Scan Explanation**\n" + ("The model's score is a yes/no signal. " * 60)
    assert len(long_answer) > 1500
    resp = client.post("/api/chat", json={
        "scan_id": uid,
        "user_message": "Where is the heatmap focused?",
        "conversation_history": [
            {"role": "user", "content": "Explain the result in simple terms"},
            {"role": "assistant", "content": long_answer},
        ],
    })
    assert resp.status_code == 200, resp.text
