"""Test helper: sign a TestClient in with one of the built-in demo accounts."""

DEMO_PASSWORDS = {
    "dr_sterling": "ClinicianSec2026!",
    "officer_clara": "PrivacySec2026!",
    "admin_sec": "AdminSec2026!",
}


def authenticate(client, username: str = "admin_sec"):
    """Logs in and attaches the bearer token to every later request made by `client`."""
    resp = client.post("/api/v1/auth/login", data={"username": username, "password": DEMO_PASSWORDS[username]})
    assert resp.status_code == 200, resp.text
    client.headers.update({"Authorization": f"Bearer {resp.json()['access_token']}"})
    return client
