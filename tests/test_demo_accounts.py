"""Demo accounts are on in development, off in production, and real users come from MEDSHIELD_USERS_JSON."""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from medshield.auth import users as users_module
from medshield.auth.security import hash_password
from medshield.config import get_settings


@pytest.fixture
def fresh_users(monkeypatch):
    """Rebuild the user registry from the current environment, then restore the default afterwards."""
    def rebuild(**env):
        for key in ("MEDSHIELD_ENVIRONMENT", "MEDSHIELD_ENABLE_DEMO_USERS", "MEDSHIELD_USERS_JSON",
                    "MEDSHIELD_SECRET_PEPPER", "MEDSHIELD_JWT_SECRET_KEY"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        users_module.reset_user_db()
        return users_module

    yield rebuild
    monkeypatch.undo()
    get_settings.cache_clear()
    users_module.reset_user_db()


PRODUCTION = {
    "MEDSHIELD_ENVIRONMENT": "production",
    "MEDSHIELD_SECRET_PEPPER": "p" * 40,
    "MEDSHIELD_JWT_SECRET_KEY": "j" * 40,
}


def test_demo_accounts_available_in_development(fresh_users):
    users = fresh_users()
    assert users.demo_users_enabled()
    assert users.authenticate_user("admin_sec", "AdminSec2026!") is not None


def test_demo_accounts_disabled_by_default_in_production(fresh_users):
    users = fresh_users(**PRODUCTION)
    assert not users.demo_users_enabled()
    assert users.authenticate_user("admin_sec", "AdminSec2026!") is None


def test_demo_accounts_can_be_enabled_explicitly_in_production(fresh_users):
    users = fresh_users(**PRODUCTION, MEDSHIELD_ENABLE_DEMO_USERS="true")
    assert users.authenticate_user("dr_sterling", "ClinicianSec2026!") is not None


def test_production_users_from_env_json(fresh_users):
    record = {"username": "dr_patel", "email": "p@example.org", "full_name": "Dr. Patel", "role": "clinician",
              "hashed_password": hash_password("correct horse battery"), "disabled": False}
    users = fresh_users(**PRODUCTION, MEDSHIELD_USERS_JSON=json.dumps([record]))
    assert users.authenticate_user("dr_patel", "correct horse battery") is not None
    assert users.authenticate_user("dr_patel", "wrong password") is None


def test_invalid_users_json_is_logged_not_silently_ignored(fresh_users, caplog):
    with caplog.at_level(logging.ERROR, logger="medshield.auth.users"):
        fresh_users(**PRODUCTION, MEDSHIELD_USERS_JSON="{not json")
    assert "MEDSHIELD_USERS_JSON could not be loaded" in caplog.text


def test_options_endpoint_is_public_and_reflects_setting(fresh_users):
    from medshield.api.app import create_app
    from medshield.config import Settings

    fresh_users(**PRODUCTION)
    settings = Settings(require_mtls=True)          # public even when mTLS is enforced
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    resp = TestClient(app).get("/api/v1/auth/options")
    assert resp.status_code == 200
    assert resp.json() == {"demo_accounts_enabled": False}


def test_api_docs_hidden_in_production(fresh_users):
    from medshield.api.app import create_app
    from medshield.config import Settings

    fresh_users(**PRODUCTION)
    prod = TestClient(create_app(Settings()))
    assert prod.get("/openapi.json").status_code == 404
    dev = TestClient(create_app(Settings(environment="development")))
    assert dev.get("/openapi.json").status_code == 200
