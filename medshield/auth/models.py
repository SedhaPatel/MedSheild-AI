from typing import List, Optional
from pydantic import BaseModel, Field

ROLE_CLINICIAN = "clinician"
ROLE_PRIVACY_OFFICER = "privacy_officer"
ROLE_ADMIN = "admin"

ALL_ROLES = [ROLE_CLINICIAN, ROLE_PRIVACY_OFFICER, ROLE_ADMIN]


class UserPublic(BaseModel):
    username: str
    email: str
    full_name: str
    role: str
    disabled: bool = False
    assigned_study_uids: List[str] = Field(default_factory=list)


class UserInDB(UserPublic):
    hashed_password: str


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=256)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserPublic


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

