from sqlalchemy.orm import Session
from typing import Optional, List # Added List for return type hinting
from fastapi import HTTPException # For raising errors in update_user

from app.models.sql_models import User
from app.schemas.user_schemas import UserCreate, UserUpdate # Added UserUpdate
from app.core.security import get_password_hash, verify_password # Added verify_password

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user: UserCreate) -> User:
    # This function is used for both general user registration and staff creation by an admin.
    # The role and tenant_id validation should ideally happen at the router level before calling this service.
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=hashed_password,
        role=user.role.value, # UserCreate uses UserRoleEnum (str-based)
        tenant_id=user.tenant_id,
        is_active=True # Default to active
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user: User, user_update: UserUpdate) -> User:
    if user_update.username:
        existing_user = get_user_by_username(db, user_update.username)
        if existing_user and existing_user.id != user.id:
            raise HTTPException(status_code=400, detail="Username already taken")
        user.username = user_update.username
    if user_update.email:
        existing_user = get_user_by_email(db, user_update.email)
        if existing_user and existing_user.id != user.id:
            raise HTTPException(status_code=400, detail="Email already taken")
        user.email = user_update.email # type: ignore

    if user_update.new_password:
        if not user_update.current_password:
            raise HTTPException(status_code=400, detail="Current password is required to set a new password")
        if not verify_password(user_update.current_password, user.password_hash): # type: ignore
            raise HTTPException(status_code=400, detail="Incorrect current password")
        user.password_hash = get_password_hash(user_update.new_password)

    # Note: is_active and role are not updated here, should be handled by specific admin functions if needed.
    # For example, an admin updating a staff member's role or active status.

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_users_by_tenant(db: Session, tenant_id: int, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).filter(User.tenant_id == tenant_id).offset(skip).limit(limit).all()

def get_user_by_id_and_tenant(db: Session, user_id: int, tenant_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
