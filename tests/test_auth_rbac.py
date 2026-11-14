from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from medshield.api.app import create_app
from medshield.auth.dependencies import register_study_owner, clear_study_owners
from medshield.auth.models import ROLE_ADMIN, ROLE_CLINICIAN, ROLE_PRIVACY_OFFICER
from medshield.auth.security import create_access_token
from medshield.auth.users import reset_user_db
from medshield.config import Settings, get_settings


from medshield.api.routes.dashboard import _dashboard_kms, _dashboard_worklist, _dashboard_session_cache


@pytest.fixture(autouse=True)
def setup_auth_environment():
    reset_user_db()
    clear_study_owners()
    _dashboard_kms._keys.clear()
    _dashboard_kms._revoked.clear()
    _dashboard_worklist.clear()
    _dashboard_session_cache.clear()
    yield
    clear_study_owners()
    _dashboard_kms._keys.clear()
    _dashboard_kms._revoked.clear()
    _dashboard_worklist.clear()
    _dashboard_session_cache.clear()


@pytest.fixture
def auth_client(tmp_path):
    storage_dir = str(tmp_path / "enc_studies")
    settings = Settings(
        storage_path=storage_dir,
        require_mtls=False,
        secret_pepper=b"test-salt-auth-rbac-1",
        jwt_secret_key="TestSecretKeyForTestingPurposesOnly2026-AtLeast32Chars!",
        jwt_access_token_expire_minutes=60,
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    return client, settings


def test_auth_login_success_and_cookie(auth_client):
    client, settings = auth_client
    # Login as Dr. Sterling (Clinician)
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "dr_sterling", "password": "ClinicianSec2026!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == ROLE_CLINICIAN
    assert data["user"]["username"] == "dr_sterling"
    assert "auth_token" in resp.cookies


def test_auth_login_invalid_password(auth_client):
    client, _ = auth_client
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "dr_sterling", "password": "WrongPassword123!"},
    )
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.json()["detail"]


def test_auth_login_nonexistent_user(auth_client):
    client, _ = auth_client
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "ghost_user", "password": "AnyPassword!"},
    )
    assert resp.status_code == 401


def test_get_current_user_profile(auth_client):
    client, settings = auth_client
    token = create_access_token({"sub": "officer_clara", "role": ROLE_PRIVACY_OFFICER}, settings=settings)
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "officer_clara"
    assert data["role"] == ROLE_PRIVACY_OFFICER


def test_missing_token_returns_401(auth_client):
    client, _ = auth_client
    # Testing endpoints that require authentication
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/dashboard/samples").status_code == 401
    assert client.get("/api/v1/dashboard/worklist").status_code == 401
    assert client.post("/api/v1/dashboard/analyze", data={"sample_id": "patient_01_pneumonia"}).status_code == 401
    assert client.post("/api/v1/studies").status_code == 401
    assert client.post("/api/chat", json={"scan_id": "123", "user_message": "hi"}).status_code == 401


def test_invalid_token_signature_returns_401(auth_client):
    client, _ = auth_client
    invalid_token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiJkcl9zdGVybGluZyIsInJvbGUiOiJjbGluaWNpYW4ifQ."
        "invalidsignaturethatwillnotmatchthesecretkey1234567890"
    )
    resp = client.get("/api/v1/dashboard/samples", headers={"Authorization": f"Bearer {invalid_token}"})
    assert resp.status_code == 401
    assert "Invalid token" in resp.json()["detail"]


def test_expired_token_returns_401(auth_client):
    client, settings = auth_client
    expired_token = create_access_token(
        {"sub": "dr_sterling", "role": ROLE_CLINICIAN},
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
        settings=settings,
    )
    resp = client.get("/api/v1/dashboard/samples", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


def test_spoofed_certificate_header_without_jwt_is_rejected(auth_client):
    client, settings = auth_client
    # Even if attacker provides spoofed X-Client-Cert-SHA256 header, missing JWT returns 401
    resp = client.post(
        "/api/v1/dashboard/analyze",
        data={"sample_id": "patient_01_pneumonia"},
        headers={"X-Client-Cert-SHA256": "any-mock-fingerprint"},
    )
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]


def test_clinician_cannot_perform_admin_user_management(auth_client):
    client, settings = auth_client
    clinician_token = create_access_token({"sub": "dr_sterling", "role": ROLE_CLINICIAN}, settings=settings)
    headers = {"Authorization": f"Bearer {clinician_token}"}

    # Clinician attempts to list all users -> 403 Forbidden
    list_resp = client.get("/api/v1/auth/users", headers=headers)
    assert list_resp.status_code == 403
    assert "Forbidden" in list_resp.json()["detail"]

    # Clinician attempts to create a user -> 403 Forbidden
    create_resp = client.post(
        "/api/v1/auth/users",
        json={
            "username": "rogue_user",
            "password": "Password123!",
            "full_name": "Rogue Account",
            "email": "rogue@apexhealth.org",
            "role": "admin",
        },
        headers=headers,
    )
    assert create_resp.status_code == 403


def test_admin_can_perform_user_management(auth_client):
    client, settings = auth_client
    admin_token = create_access_token({"sub": "admin_sec", "role": ROLE_ADMIN}, settings=settings)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin lists users -> 200
    list_resp = client.get("/api/v1/auth/users", headers=headers)
    assert list_resp.status_code == 200
    usernames = [u["username"] for u in list_resp.json()]
    assert "dr_sterling" in usernames
    assert "admin_sec" in usernames

    # Admin creates a new clinician
    create_resp = client.post(
        "/api/v1/auth/users",
        json={
            "username": "dr_house",
            "password": "DiagnosticHouse2026!",
            "full_name": "Dr. Gregory House",
            "email": "house@apexhealth.org",
            "role": "clinician",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["username"] == "dr_house"

    # New clinician can log in
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "dr_house", "password": "DiagnosticHouse2026!"},
    )
    assert login_resp.status_code == 200


def test_clinician_cannot_crypto_shred_studies(auth_client):
    client, settings = auth_client
    clinician_token = create_access_token({"sub": "dr_sterling", "role": ROLE_CLINICIAN}, settings=settings)
    clinician_headers = {"Authorization": f"Bearer {clinician_token}"}

    # 1. Ingest a study as clinician
    ingest_resp = client.post(
        "/api/v1/dashboard/analyze",
        data={"sample_id": "patient_01_pneumonia"},
        headers=clinician_headers,
    )
    assert ingest_resp.status_code == 200
    uid = ingest_resp.json()["anonymous_study_instance_uid"]

    # 2. Clinician attempts to execute irreversible crypto-shredding -> 403 Forbidden!
    shred_resp = client.post(
        f"/api/v1/dashboard/shred/{uid}",
        headers=clinician_headers,
    )
    assert shred_resp.status_code == 403
    assert "Forbidden" in shred_resp.json()["detail"]


def test_privacy_officer_can_crypto_shred_study(auth_client):
    client, settings = auth_client
    clinician_token = create_access_token({"sub": "dr_sterling", "role": ROLE_CLINICIAN}, settings=settings)
    privacy_token = create_access_token({"sub": "officer_clara", "role": ROLE_PRIVACY_OFFICER}, settings=settings)

    # 1. Ingest study
    ingest_resp = client.post(
        "/api/v1/dashboard/analyze",
        data={"sample_id": "patient_01_pneumonia"},
        headers={"Authorization": f"Bearer {clinician_token}"},
    )
    assert ingest_resp.status_code == 200
    uid = ingest_resp.json()["anonymous_study_instance_uid"]

    # 2. Privacy officer triggers Right to Erasure crypto-shredding -> 200
    shred_resp = client.post(
        f"/api/v1/dashboard/shred/{uid}",
        headers={"Authorization": f"Bearer {privacy_token}"},
    )
    assert shred_resp.status_code == 200
    assert shred_resp.json()["status"] == "CRYPTO_SHREDDED"
    assert shred_resp.json()["math_erasure_verified"] is True


def test_study_level_authorization_isolation(auth_client):
    client, settings = auth_client
    from medshield.auth.users import add_user
    add_user("dr_other", "OtherSec2026!", "Dr. Other", "other@apexhealth.org", ROLE_CLINICIAN)
    dr_sterling_token = create_access_token({"sub": "dr_sterling", "role": ROLE_CLINICIAN}, settings=settings)
    dr_other_token = create_access_token({"sub": "dr_other", "role": ROLE_CLINICIAN}, settings=settings)

    # Ingest a study owned by dr_sterling
    ingest_resp = client.post(
        "/api/v1/dashboard/analyze",
        data={"sample_id": "patient_01_pneumonia"},
        headers={"Authorization": f"Bearer {dr_sterling_token}"},
    )
    assert ingest_resp.status_code == 200
    sterling_uid = ingest_resp.json()["anonymous_study_instance_uid"]

    # dr_sterling can access DICOM and chat
    dicom_sterling = client.get(
        f"/api/v1/dashboard/studies/{sterling_uid}/dicom",
        headers={"Authorization": f"Bearer {dr_sterling_token}"},
    )
    assert dicom_sterling.status_code == 200

    # dr_other tries to guess and access dr_sterling's study -> 403 Forbidden
    dicom_other = client.get(
        f"/api/v1/dashboard/studies/{sterling_uid}/dicom",
        headers={"Authorization": f"Bearer {dr_other_token}"},
    )
    assert dicom_other.status_code == 403
    assert "not authorized" in dicom_other.json()["detail"].lower()

    # dr_other tries to query chat on dr_sterling's study -> 403 Forbidden
    chat_other = client.post(
        "/api/chat",
        json={"scan_id": sterling_uid, "user_message": "Read patient data"},
        headers={"Authorization": f"Bearer {dr_other_token}"},
    )
    assert chat_other.status_code == 403


def test_public_health_check_requires_no_auth(auth_client):
    client, _ = auth_client
    # Genuinely public endpoint
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "HEALTHY"
