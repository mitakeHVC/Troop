"""
Service layer for tenant management.

This module handles the business logic for creating and retrieving tenants.
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.sql_models import Tenant
from app.schemas.tenant_schemas import TenantCreate
from fastapi import HTTPException, status # Added for potential future use

def get_tenant_by_id(db: Session, tenant_id: int) -> Optional[Tenant]:
    """
    Retrieves a tenant by its ID.

    Args:
        db: SQLAlchemy database session.
        tenant_id: ID of the tenant to retrieve.

    Returns:
        The Tenant object if found, else None.
    """
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()

def get_tenant_by_name(db: Session, name: str) -> Optional[Tenant]:
    """
    Retrieves a tenant by its name.

    Args:
        db: SQLAlchemy database session.
        name: Name of the tenant to search for.

    Returns:
        The Tenant object if found, else None.
    """
    return db.query(Tenant).filter(Tenant.name == name).first()

def get_tenants(db: Session, skip: int = 0, limit: int = 100) -> List[Tenant]:
    """
    Retrieves a list of tenants, with optional pagination.

    Args:
        db: SQLAlchemy database session.
        skip: Number of records to skip (for pagination).
        limit: Maximum number of records to return (for pagination).

    Returns:
        A list of Tenant objects.
    """
    return db.query(Tenant).order_by(Tenant.id).offset(skip).limit(limit).all()

def create_tenant(db: Session, tenant_in: TenantCreate) -> Tenant:
    """
    Creates a new tenant.
    Note: Duplicate name check should be handled by the calling router/endpoint
    by first calling `get_tenant_by_name`.

    Args:
        db: SQLAlchemy database session.
        tenant_in: Pydantic schema with tenant creation data.

    Returns:
        The newly created Tenant object.
    """
    # Duplicate name check is expected to be done in the router before calling this.
    # If adding here:
    # if get_tenant_by_name(db, name=tenant_in.name):
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant name already exists.")

    db_tenant = Tenant(name=tenant_in.name)
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant
