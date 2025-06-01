"""
Service layer for user management.

This module handles the business logic for creating, retrieving,
and updating users.
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from fastapi import HTTPException, status # Added status import

from app.models.sql_models import User
from app.schemas.user_schemas import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    Retrieves a user by their username.

    Args:
        db: SQLAlchemy database session.
        username: Username to search for.

    Returns:
        The User object if found, else None.
    """
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Retrieves a user by their email address.

    Args:
        db: SQLAlchemy database session.
        email: Email address to search for.

    Returns:
        The User object if found, else None.
    """
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user_in: UserCreate) -> User:
    """
    Creates a new user.
    This function is used for both general user registration and staff creation by an admin.
    Role and tenant_id validation should ideally happen at the router level before calling this service.

    Args:
        db: SQLAlchemy database session.
        user_in: Pydantic schema with user creation data.

    Returns:
        The newly created User object.
    """
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=hashed_password,
        role=user_in.role.value, # UserCreate uses UserRoleEnum (str-based Pydantic enum)
        tenant_id=user_in.tenant_id,
        is_active=True # Default to active
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, db_user: User, user_update_data: UserUpdate) -> User:
    """
    Updates an existing user's profile information (username, email, password).
    Role and active status are not updated by this function; typically handled by admin-specific functions.

    Args:
        db: SQLAlchemy database session.
        db_user: The existing User ORM instance to update.
        user_update_data: Pydantic schema with user update data.

    Raises:
        HTTPException (400): If username/email is already taken by another user,
                             or if current password is required but not provided/incorrect for password change.
    Returns:
        The updated User object.
    """
    if user_update_data.username:
        existing_user = get_user_by_username(db, user_update_data.username)
        if existing_user and existing_user.id != db_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")
        db_user.username = user_update_data.username # type: ignore

    if user_update_data.email:
        existing_user = get_user_by_email(db, user_update_data.email)
        if existing_user and existing_user.id != db_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already taken")
        db_user.email = user_update_data.email # type: ignore

    if user_update_data.new_password:
        if not user_update_data.current_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is required to set a new password")
        if not verify_password(user_update_data.current_password, db_user.password_hash): # type: ignore
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password")
        db_user.password_hash = get_password_hash(user_update_data.new_password) # type: ignore

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_users_by_tenant(db: Session, tenant_id: int, skip: int = 0, limit: int = 100) -> List[User]:
    """
    Retrieves a list of users for a given tenant, with optional pagination.

    Args:
        db: SQLAlchemy database session.
        tenant_id: ID of the tenant.
        skip: Number of records to skip.
        limit: Maximum number of records to return.

    Returns:
        A list of User objects.
    """
    return db.query(User).filter(User.tenant_id == tenant_id).order_by(User.id).offset(skip).limit(limit).all()

def get_user_by_id_and_tenant(db: Session, user_id: int, tenant_id: int) -> Optional[User]:
    """
    Retrieves a specific user by their ID and tenant ID.

    Args:
        db: SQLAlchemy database session.
        user_id: ID of the user.
        tenant_id: ID of the tenant.

    Returns:
        The User object if found and belongs to the tenant, else None.
    """
    return db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
