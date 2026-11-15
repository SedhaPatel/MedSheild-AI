from datetime import timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from medshield.auth.dependencies import get_current_user, require_admin
from medshield.auth.models import LoginRequest, Token, UserPublic
from medshield.auth.security import create_access_token
from medshield.auth.users import add_user, authenticate_user, list_users
from medshield.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & Access Control"])


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=100)
    role: str = Field(..., pattern="^(clinician|privacy_officer|admin)$")


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
):
    """
    Authenticate user with username and password.
    Accepts both application/json and application/x-www-form-urlencoded payloads.
    Returns signed JWT access token and sets secure HttpOnly cookie.
    """
    username = None
    password = None
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                username = body.get("username")
                password = body.get("password")
        except Exception:
            pass
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        try:
            form = await request.form()
            username = form.get("username")
            password = form.get("password")
        except Exception:
            pass
    else:
        try:
            body = await request.json()
            if isinstance(body, dict):
                username = body.get("username")
                password = body.get("password")
        except Exception:
            try:
                form = await request.form()
                username = form.get("username")
                password = form.get("password")
            except Exception:
                pass

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing username or password in login request",
        )

    user = authenticate_user(str(username), str(password))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=expires_delta,
        settings=settings,
    )

    # Set HttpOnly cookie for browser sessions
    response.set_cookie(
        key="auth_token",
        value=access_token,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.environment.lower() == "production",
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in_seconds=settings.jwt_access_token_expire_minutes * 60,
        user=user,
    )


@router.get("/me", response_model=UserPublic)
async def get_my_profile(
    current_user: UserPublic = Depends(get_current_user),
):
    """Retrieve authenticated user's profile and active role."""
    return current_user


@router.post("/logout")
async def logout(response: Response):
    """Log out by clearing the session auth cookie."""
    response.delete_cookie(key="auth_token")
    return {"status": "LOGGED_OUT", "message": "Session invalidated"}


@router.get("/users", response_model=List[UserPublic])
async def list_all_users(
    admin_user: UserPublic = Depends(require_admin),
):
    """List all registered system users and assigned roles (Admin only)."""
    return list_users()


@router.post("/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    req: CreateUserRequest,
    admin_user: UserPublic = Depends(require_admin),
):
    """Create a new user with bcrypt password hashing (Admin only)."""
    try:
        new_user = add_user(
            username=req.username,
            password=req.password,
            full_name=req.full_name,
            email=req.email,
            role=req.role,
        )
        return new_user
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

