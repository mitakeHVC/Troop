"""
API router for managing pickup time slots.

Provides endpoints for:
- Tenant admins to create, list, retrieve, update, and delete time slots for their tenant.
- Public/Authenticated users to list available time slots for a specific tenant.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from app.db.session import get_db
from app.models.sql_models import User
from app.models.sql_models import UserRole as DBUserRoleEnum
from app.schemas.timeslot_schemas import PickupTimeSlotCreate, PickupTimeSlotResponse, PickupTimeSlotUpdate
from app.services import timeslot_service
from app.api import deps

router = APIRouter()

@router.post("/", response_model=PickupTimeSlotResponse, status_code=status.HTTP_201_CREATED)
def create_new_pickup_timeslot(
    timeslot_create_data: PickupTimeSlotCreate, # Renamed
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    """
    Create a new pickup time slot for the authenticated tenant admin's tenant.
    Super_admins should use tenant-specific administrative routes for timeslot creation.
    """
    if current_user.role == DBUserRoleEnum.super_admin:
        # This endpoint is tenant-implicit based on authenticated tenant_admin.
        # Super_admins needing to create slots for arbitrary tenants should use a different,
        # tenant-explicit endpoint (e.g., /admin/tenants/{tenant_id}/timeslots).
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admins should use a tenant-specific route for creating timeslots.")

    if not current_user.tenant_id: # Should be guaranteed by dependency if not super_admin
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin must be associated with a tenant.")

    return timeslot_service.create_timeslot(db=db, timeslot_create_data=timeslot_create_data, tenant_id=current_user.tenant_id)

@router.get("/tenant/{tenant_id}/available", response_model=List[PickupTimeSlotResponse])
def list_available_timeslots_for_tenant(
    tenant_id: int = Path(..., description="The ID of the tenant whose available time slots are to be retrieved."),
    date_from: Optional[datetime.date] = Query(None, description="Filter slots from this date (YYYY-MM-DD)"),
    date_to: Optional[datetime.date] = Query(None, description="Filter slots up to this date (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200), # Added sensible limits
    db: Session = Depends(get_db),
    # No specific authentication required for this, public or any authenticated user can view.
):
    """
    List active and available pickup time slots for a specific tenant.
    This endpoint is typically public or accessible to all authenticated users.
    """
    # Optional: Add a service call here to validate tenant_id exists and is active.
    # e.g., tenant = tenant_service.get_tenant_by_id(db, tenant_id); if not tenant: raise HTTPException(...)

    slots = timeslot_service.get_timeslots_by_tenant(
        db, tenant_id=tenant_id, skip=skip, limit=limit,
        date_from=date_from, date_to=date_to,
        only_available=True, is_active=True
    )
    return slots

@router.get("/", response_model=List[PickupTimeSlotResponse])
def read_all_timeslots_for_current_admin( # Renamed for clarity
    target_tenant_id_for_superadmin: Optional[int] = Query(None, description="Super_admin must use this to specify tenant."),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin) # Ensures tenant_admin or super_admin
):
    """
    List all pickup time slots for the current tenant admin.
    Super_admins can use this by providing `target_tenant_id_for_superadmin`.
    """
    effective_tenant_id: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
        if target_tenant_id_for_superadmin is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin must specify 'target_tenant_id_for_superadmin' query parameter to list timeslots.")
        effective_tenant_id = target_tenant_id_for_superadmin
    else: # Must be tenant_admin (guaranteed by dependency)
        if not current_user.tenant_id: # Should not be reached if dependency works
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
        effective_tenant_id = current_user.tenant_id

    slots = timeslot_service.get_timeslots_by_tenant(
        db, tenant_id=effective_tenant_id, skip=skip, limit=limit,
        date_from=date_from, date_to=date_to, is_active=is_active, only_available=False # Admin sees all
    )
    return slots

@router.get("/{timeslot_id}", response_model=PickupTimeSlotResponse)
def read_timeslot_by_id_for_current_admin( # Renamed for clarity
    timeslot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    """
    Retrieve a specific pickup time slot by ID for the current tenant admin.
    Super_admins should use tenant-specific administrative routes for this action.
    """
    effective_tenant_id: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin timeslot view needs a specific tenant context route (e.g., /admin/tenants/{id}/timeslots/{slot_id}).")

    if not current_user.tenant_id:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
    effective_tenant_id = current_user.tenant_id

    db_timeslot = timeslot_service.get_timeslot_by_id(db, timeslot_id=timeslot_id, tenant_id=effective_tenant_id)
    if db_timeslot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pickup time slot not found for your tenant.")
    return db_timeslot

@router.put("/{timeslot_id}", response_model=PickupTimeSlotResponse)
def update_existing_timeslot(
    timeslot_id: int,
    timeslot_update_data: PickupTimeSlotUpdate, # Renamed
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    """
    Update an existing pickup time slot for the current tenant admin.
    Super_admins should use tenant-specific administrative routes.
    """
    effective_tenant_id: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin timeslot update needs a specific tenant context route.")

    if not current_user.tenant_id:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
    effective_tenant_id = current_user.tenant_id

    db_timeslot = timeslot_service.get_timeslot_by_id(db, timeslot_id=timeslot_id, tenant_id=effective_tenant_id)
    if db_timeslot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pickup time slot not found for your tenant.")

    return timeslot_service.update_timeslot(db=db, db_timeslot=db_timeslot, timeslot_update_data=timeslot_update_data) # Pass renamed var

@router.delete("/{timeslot_id}", response_model=PickupTimeSlotResponse)
def delete_existing_timeslot(
    timeslot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    """
    Delete an existing pickup time slot for the current tenant admin.
    Super_admins should use tenant-specific administrative routes.
    """
    effective_tenant_id: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin timeslot deletion needs a specific tenant context route.")

    if not current_user.tenant_id:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
    effective_tenant_id = current_user.tenant_id

    db_timeslot = timeslot_service.get_timeslot_by_id(db, timeslot_id=timeslot_id, tenant_id=effective_tenant_id)
    if db_timeslot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pickup time slot not found for your tenant.")

    return timeslot_service.delete_timeslot(db=db, db_timeslot=db_timeslot)
