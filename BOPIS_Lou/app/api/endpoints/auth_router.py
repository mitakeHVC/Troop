"""
API router for authentication-related operations, including user registration,
login (token issuance), and token refresh.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional # Imported for Optional type hint

from app.schemas.user_schemas import UserCreate, UserResponse, UserLogin
from app.schemas.token_schemas import Token, RefreshTokenRequest, TokenPayload
from app.services import user_service
from app.core.security import verify_password, create_access_token, create_refresh_token, verify_token
from app.db.session import get_db
from app.models.sql_models import User

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)): # Renamed user to user_in
    """
    Register a new user.
    - Validates that username and email are unique.
    - Requires `tenant_id` for non-super_admin roles.
    - `super_admin` role cannot have a `tenant_id`.
    """
    db_user_by_username = user_service.get_user_by_username(db, username=user_in.username)
    if db_user_by_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    db_user_by_email = user_service.get_user_by_email(db, email=user_in.email)
    if db_user_by_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    if user_in.role.value != "super_admin" and user_in.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID is required for non-super_admin roles")
    if user_in.role.value == "super_admin":
        user_in.tenant_id = None

    created_user = user_service.create_user(db=db, user_in=user_in) # Pass user_in
    return created_user

@router.post("/login", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Authenticate user and return JWT access and refresh tokens.
    Login can be performed using either username or email.
    """
    user = user_service.get_user_by_username(db, username=form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        user = user_service.get_user_by_email(db, email=form_data.username) # Try by email
        if not user or not verify_password(form_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username, email, or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

    access_token = create_access_token(subject=user.id, role=user.role.value, tenant_id=user.tenant_id) # type: ignore
    refresh_token = create_refresh_token(subject=user.id, role=user.role.value, tenant_id=user.tenant_id) # type: ignore
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@router.post("/refresh-token", response_model=Token)
def refresh_access_token(refresh_request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh an access token using a valid refresh token.
    """
    token_data: Optional[TokenPayload] = verify_token(refresh_request.refresh_token)
    if not token_data or token_data.type != "refresh": # Ensure it's a refresh token
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    if token_data.sub is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload: missing subject")

    user = db.query(User).filter(User.id == int(token_data.sub)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User associated with token not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")


    access_token = create_access_token(subject=user.id, role=user.role.value, tenant_id=user.tenant_id) # type: ignore
    # For enhanced security, a new refresh token could also be issued here (sliding window)
    # For simplicity, current refresh token is re-used if still valid.
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_request.refresh_token}
