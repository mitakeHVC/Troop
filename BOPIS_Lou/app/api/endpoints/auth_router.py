from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm # For login form
from sqlalchemy.orm import Session

from app.schemas.user_schemas import UserCreate, UserResponse, UserLogin
from app.schemas.token_schemas import Token, RefreshTokenRequest, TokenPayload # Added TokenPayload for verify_token hint
from app.services import user_service
from app.core.security import verify_password, create_access_token, create_refresh_token, verify_token
from app.db.session import get_db
from app.models.sql_models import User # For type hinting and accessing user.role.value

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user_by_username = user_service.get_user_by_username(db, username=user.username)
    if db_user_by_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    db_user_by_email = user_service.get_user_by_email(db, email=user.email)
    if db_user_by_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Basic validation for tenant_id based on role
    if user.role.value != "super_admin" and user.tenant_id is None: # Use user.role.value
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID is required for non-super_admin roles")
    if user.role.value == "super_admin": # Super_admin should not have a tenant_id. Use user.role.value
        user.tenant_id = None

    created_user = user_service.create_user(db=db, user=user)
    # Ensure the response matches UserResponse, which expects role as an enum member, not raw string.
    # The UserResponse model with orm_mode=True should handle this conversion if user.role is the DB enum.
    # If created_user.role is a string from UserCreate, it should be fine as UserResponse.role is UserRoleEnum.
    return created_user

@router.post("/login", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = user_service.get_user_by_username(db, username=form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        # Try by email if username fails
        user = user_service.get_user_by_email(db, email=form_data.username)
        if not user or not verify_password(form_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username, email, or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # user.role is SQLAlchemy enum, user.role.value is its string value
    access_token = create_access_token(subject=user.id, role=user.role.value, tenant_id=user.tenant_id)
    refresh_token = create_refresh_token(subject=user.id, role=user.role.value, tenant_id=user.tenant_id)
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@router.post("/refresh-token", response_model=Token)
def refresh_access_token(refresh_request: RefreshTokenRequest, db: Session = Depends(get_db)):
    token_data: Optional[TokenPayload] = verify_token(refresh_request.refresh_token) # Type hint for clarity
    if not token_data or token_data.type != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    if token_data.sub is None: # Ensure sub is not None
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.id == int(token_data.sub)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found for token")

    # Generate new access token
    # user.role is SQLAlchemy enum, user.role.value is its string value
    access_token = create_access_token(subject=user.id, role=user.role.value, tenant_id=user.tenant_id)
    # Optionally, issue a new refresh token as well for sliding sessions, or re-use existing one
    # For simplicity, we are not re-issuing refresh token here but could.
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_request.refresh_token}
