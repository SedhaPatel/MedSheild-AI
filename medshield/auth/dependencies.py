from typing import Callable, Dict, List, Optional
from fastapi import Cookie, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from medshield.auth.models import (
    ALL_ROLES,
    ROLE_ADMIN,
    ROLE_CLINICIAN,
    ROLE_PRIVACY_OFFICER,
    UserPublic,
)
from medshield.auth.security import decode_access_token
from medshield.auth.users import get_user_by_username
from medshield.config import Settings, get_settings

security_scheme = HTTPBearer(auto_error=False)

# Study ownership registry: maps anonymous_study_instance_uid -> owner_username
_study_owners: Dict[str, str] = {}


def register_study_owner(study_uid: str, username: str) -> None:
    """Record the owner/ingesting clinician for a given study UID."""
    if study_uid and username:
        _study_owners[study_uid] = username.lower().strip()


def get_study_owner(study_uid: str) -> Optional[str]:
    return _study_owners.get(study_uid)


def clear_study_owners() -> None:
    """Clear study owner registry (for test isolation)."""
    global _study_owners
    _study_owners = {}


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    auth_token_cookie: Optional[str] = Cookie(default=None, alias="auth_token"),
    token_query: Optional[str] = Query(default=None, alias="token"),
    settings: Settings = Depends(get_settings),
) -> UserPublic:
    """
    Extract and validate JWT access token from:
    1. Authorization: Bearer <token> header
    2. auth_token HttpOnly cookie
    3. token query parameter (for DICOM stream and heatmap media fetches)
    """
    token: Optional[str] = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif auth_token_cookie:
        token = auth_token_cookie
    elif token_query:
        token = token_query

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token, settings=settings)
    username: Optional[str] = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Subject missing in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: User '{username}' not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Account has been disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserPublic(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        disabled=user.disabled,
        assigned_study_uids=user.assigned_study_uids,
    )


def require_roles(allowed_roles: List[str]) -> Callable:
    """FastAPI dependency factory enforcing Role-Based Access Control."""
    async def role_checker(
        current_user: UserPublic = Depends(get_current_user),
    ) -> UserPublic:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Role '{current_user.role}' lacks permission. Required roles: {allowed_roles}",
            )
        return current_user

    return role_checker


# Reusable role-based dependencies
require_clinician = require_roles([ROLE_CLINICIAN, ROLE_ADMIN])
require_privacy_officer = require_roles([ROLE_PRIVACY_OFFICER, ROLE_ADMIN])
require_admin = require_roles([ROLE_ADMIN])
require_authenticated_user = require_roles(ALL_ROLES)


def check_study_access(study_uid: str, user: UserPublic) -> bool:
    """
    Verify whether user is authorized to access the study:
    - Admins and Privacy Officers can access all studies for oversight & right-to-erasure audits.
    - Clinicians can access studies they ingested, studies explicitly assigned to them,
      or reference samples that have not been restricted to another user.
    """
    if user.role in (ROLE_ADMIN, ROLE_PRIVACY_OFFICER):
        return True

    owner = get_study_owner(study_uid)
    if owner is None:
        # Study is an unassigned reference sample or legacy study
        return True

    if owner == user.username.lower().strip():
        return True

    if study_uid in user.assigned_study_uids:
        return True

    return False


async def verify_study_access(
    study_uid: str,
    current_user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    """FastAPI dependency verifying study-level authorization."""
    if not check_study_access(study_uid, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: User '{current_user.username}' is not authorized to access study '{study_uid}'",
        )
    return current_user

