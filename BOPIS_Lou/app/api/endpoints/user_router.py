from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.user_schemas import UserResponse, UserUpdate
from app.services import user_service
from app.api import deps # For RBAC
from app.models.sql_models import User # For type hinting current_user

router = APIRouter()

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(deps.get_current_user)):
    # The UserResponse schema expects role to be UserRoleEnum.
    # current_user.role is DBUserRoleEnum.
    # Pydantic's orm_mode and UserResponse definition should handle this.
    return current_user

@router.put("/me", response_model=UserResponse)
def update_user_me(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    # User can only update their own username, email, password via this endpoint.
    # Role or tenant_id cannot be changed here by the user themselves.
    # is_active is also not changed here.

    # Prevent users from trying to change fields not allowed in this endpoint through UserUpdate
    if hasattr(user_update, 'role') and user_update.role is not None: # type: ignore
        raise HTTPException(status_code=400, detail="Cannot change role via this endpoint.")
    if hasattr(user_update, 'is_active') and user_update.is_active is not None: # type: ignore
        raise HTTPException(status_code=400, detail="Cannot change active status via this endpoint.")

    updated_user = user_service.update_user(db=db, user=current_user, user_update=user_update)
    return updated_user
