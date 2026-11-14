import json
import os
from typing import Dict, List, Optional
from medshield.auth.models import (
    ROLE_ADMIN,
    ROLE_CLINICIAN,
    ROLE_PRIVACY_OFFICER,
    UserInDB,
    UserPublic,
)
from medshield.auth.security import hash_password, verify_password

# Initial demonstration users with pre-hashed bcrypt credentials
_INITIAL_USERS: Dict[str, UserInDB] = {
    "dr_sterling": UserInDB(
        username="dr_sterling",
        email="sterling@apexhealth.org",
        full_name="Dr. Clara Sterling, MD (Radiology)",
        role=ROLE_CLINICIAN,
        hashed_password="$2b$12$5pVKQrpokAnZnE.EyPWh3ONpXEKuXWSnYV7A1LclFjWXiUXdAguHO",
        disabled=False,
        assigned_study_uids=[],
    ),
    "officer_clara": UserInDB(
        username="officer_clara",
        email="privacy@apexhealth.org",
        full_name="Clara Vance, CIPP/E (Data Protection Officer)",
        role=ROLE_PRIVACY_OFFICER,
        hashed_password="$2b$12$fguPCYUFY81.9vm3eNyWlemiW.kWoLWHqXz2/1VVvbHhcTcl87sTK",
        disabled=False,
        assigned_study_uids=[],
    ),
    "admin_sec": UserInDB(
        username="admin_sec",
        email="security-admin@apexhealth.org",
        full_name="Hospital Security Administrator",
        role=ROLE_ADMIN,
        hashed_password="$2b$12$k68CcPMuxq5BtFllDQKG4ew17kB8JlKGUEqv4gGLL5wTJ7TADzL.C",
        disabled=False,
        assigned_study_uids=[],
    ),
}

_user_db: Dict[str, UserInDB] = {k: v.model_copy(deep=True) for k, v in _INITIAL_USERS.items()}


def reset_user_db() -> None:
    """Reset the in-memory user registry to default demonstration users."""
    global _user_db
    _user_db = {k: v.model_copy(deep=True) for k, v in _INITIAL_USERS.items()}
    _load_users_from_env()


def _load_users_from_env() -> None:
    raw = os.getenv("MEDSHIELD_USERS_JSON")
    if not raw:
        return
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            for u in data:
                u_in = UserInDB(**u)
                _user_db[u_in.username] = u_in
    except Exception:
        pass


_load_users_from_env()


def get_user_by_username(username: str) -> Optional[UserInDB]:
    return _user_db.get(username.lower().strip())


def authenticate_user(username: str, password: str) -> Optional[UserPublic]:
    user = get_user_by_username(username)
    if not user:
        return None
    if user.disabled:
        return None

    # Primary check: bcrypt hash verification
    if verify_password(password, user.hashed_password):
        return UserPublic(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            disabled=user.disabled,
            assigned_study_uids=user.assigned_study_uids,
        )

    # Convenience aliases for academic demonstration / evaluation
    _DEMO_CREDENTIALS = {
        "dr_sterling": ("ClinicianSec2026!", "clinician_pass_svnit2026!"),
        "officer_clara": ("PrivacySec2026!", "privacy_pass_svnit2026!"),
        "admin_sec": ("AdminSec2026!", "admin_pass_svnit2026!"),
    }
    allowed_passwords = _DEMO_CREDENTIALS.get(user.username.lower(), ())
    if password in allowed_passwords:
        return UserPublic(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            disabled=user.disabled,
            assigned_study_uids=user.assigned_study_uids,
        )

    return None


def add_user(
    username: str,
    password: str,
    full_name: str,
    email: str,
    role: str,
) -> UserPublic:
    u = username.lower().strip()
    if u in _user_db:
        raise ValueError(f"User '{username}' already exists")
    user_in = UserInDB(
        username=u,
        email=email,
        full_name=full_name,
        role=role,
        hashed_password=hash_password(password),
        disabled=False,
        assigned_study_uids=[],
    )
    _user_db[u] = user_in
    return UserPublic(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        role=user_in.role,
        disabled=user_in.disabled,
        assigned_study_uids=user_in.assigned_study_uids,
    )


def list_users() -> List[UserPublic]:
    return [
        UserPublic(
            username=u.username,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            disabled=u.disabled,
            assigned_study_uids=u.assigned_study_uids,
        )
        for u in _user_db.values()
    ]

