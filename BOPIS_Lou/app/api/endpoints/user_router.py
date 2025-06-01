"""
API router for user-specific operations, such as retrieving and updating
the profile of the currently authenticated user.
"""
from fastapi import APIRouter, Depends, HTTPException, status # Added status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.user_schemas import UserResponse, UserUpdate
from app.services import user_service
from app.api import deps
from app.models.sql_models import User

router = APIRouter()

@router.get("/me", response_model=UserResponse)
def read_current_user_me(current_user: User = Depends(deps.get_current_user)):
    """
    Get profile of the currently authenticated user.
    """
    # The UserResponse schema will handle converting the User ORM model (including its DB enum for role)
    # to the appropriate Pydantic response model (which uses a Pydantic string-based enum for role).
    return current_user

@router.put("/me", response_model=UserResponse)
def update_current_user_me(
    user_update_data: UserUpdate, # Renamed for clarity
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Update the profile (username, email, password) for the currently authenticated user.
    Users cannot change their own role, active status, or tenant ID via this endpoint.
    """
    # Explicitly prevent attempts to change restricted fields, even if not in UserUpdate schema by default.
    # This is a safeguard in case UserUpdate schema changes or unexpected data is passed.
    if hasattr(user_update_data, 'role') and user_update_data.role is not None: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change 'role' via this endpoint.")
    if hasattr(user_update_data, 'is_active') and user_update_data.is_active is not None: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change 'is_active' status via this endpoint.")
    if hasattr(user_update_data, 'tenant_id') and user_update_data.tenant_id is not None: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change 'tenant_id' via this endpoint.")

    updated_user = user_service.update_user(db=db, db_user=current_user, user_update_data=user_update_data)
    return updated_user
