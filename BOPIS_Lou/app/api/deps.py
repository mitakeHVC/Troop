from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError # Corrected import order for jose
import datetime # Import the datetime module

from app.core.config import settings
# Assuming verify_token is not used directly here, but its logic is incorporated
# If verify_token from security.py IS used, it needs to be imported.
# from app.core.security import ALGORITHM, SECRET_KEY
from app.models.sql_models import User, UserRole as DBUserRoleEnum # Import DB enum
from app.schemas.token_schemas import TokenPayload
from app.db.session import get_db

# The tokenUrl should point to the actual login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login") # Assuming /auth prefix is added in main.py for auth_router

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # 'sub' should contain the user_id as a string
        user_id_str: Optional[str] = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception

        # Attempt to convert user_id to int
        try:
            user_id = int(user_id_str)
        except ValueError:
            raise credentials_exception # If sub is not a valid integer string

        # Check token type if it's part of your payload, e.g. "type": "access"
        token_type: Optional[str] = payload.get("type")
        if token_type != "access":
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        exp: Optional[int] = payload.get("exp") # JWT 'exp' is typically an int timestamp
        if exp is None:
            raise credentials_exception # No expiration time in token

        # Create TokenPayload for validation if needed, or use parts directly
        # For expiry check, directly use the 'exp' timestamp
        if datetime.datetime.utcnow() > datetime.datetime.utcfromtimestamp(exp):
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")

    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    # Attach parsed token payload to user object if needed for role/tenant_id access in dependencies
    # This is not standard, rather pass user and then check user.role, user.tenant_id
    # For RBAC, the claims are now part of the user model loaded from DB.
    # If token claims are preferred for RBAC over DB state for role/tenant:
    # user.token_role = payload.get("role")
    # user.token_tenant_id = payload.get("tenant_id")
    return user

# RBAC Dependencies
def get_current_active_superuser(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != DBUserRoleEnum.super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="The user doesn't have enough privileges (Super Admin required)"
        )
    return current_user

def get_current_active_tenant_admin(current_user: User = Depends(get_current_user)) -> User:
    # A super_admin can also manage tenant-specific resources
    if current_user.role not in [DBUserRoleEnum.tenant_admin, DBUserRoleEnum.super_admin]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="The user doesn't have enough privileges (Tenant Admin or Super Admin required)"
        )
    return current_user

# Dependency to check if the current_user is authorized for a specific tenant_id in the path
def can_manage_tenant(tenant_id: int, current_user: User = Depends(get_current_user)):
    # If current_user is super_admin, they can manage any tenant.
    if current_user.role == DBUserRoleEnum.super_admin:
        return current_user

    # If current_user is a tenant_admin, their tenant_id must match the one in the path.
    if current_user.role == DBUserRoleEnum.tenant_admin and current_user.tenant_id == tenant_id:
        return current_user

    # Otherwise, forbidden.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to manage this tenant's resources"
    )
