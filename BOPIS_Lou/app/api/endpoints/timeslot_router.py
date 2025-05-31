from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime
from app.db.session import get_db
from app.models.sql_models import User, UserRole as DBUserRoleEnum # For current_user type hint & role check
from app.schemas.timeslot_schemas import PickupTimeSlotCreate, PickupTimeSlotResponse, PickupTimeSlotUpdate
from app.services import timeslot_service
from app.api import deps

router = APIRouter()

# Endpoint for Tenant Admins to create slots for their tenant
@router.post("/", response_model=PickupTimeSlotResponse, status_code=status.HTTP_201_CREATED)
def create_new_pickup_timeslot(
    timeslot_in: PickupTimeSlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin) # Ensures tenant_admin or super_admin
):
    tenant_id_for_creation: Optional[int] = None

    if current_user.role == DBUserRoleEnum.super_admin:
        # Super_admin use case: They are not directly associated with a tenant via their user model.
        # To create a timeslot for a specific tenant, the tenant_id should be part of the path,
        # e.g., /admin/tenants/{tenant_id}/timeslots. This router is /timeslots.
        # So, this specific endpoint is better suited for tenant_admins.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admins should use a tenant-specific route (e.g., /admin/tenants/{id}/timeslots) for creating timeslots.")

    if not current_user.tenant_id: # Should be set for tenant_admin
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin must be associated with a tenant.")
    tenant_id_for_creation = current_user.tenant_id

    return timeslot_service.create_timeslot(db=db, timeslot_in=timeslot_in, tenant_id=tenant_id_for_creation)

# Endpoint for Customers and Staff to view available slots for a specific tenant
@router.get("/tenant/{tenant_id}/available", response_model=List[PickupTimeSlotResponse])
def list_available_timeslots_for_tenant(
    tenant_id: int,
    date_from: Optional[datetime.date] = Query(None, description="Filter slots from this date (YYYY-MM-DD)"),
    date_to: Optional[datetime.date] = Query(None, description="Filter slots up to this date (YYYY-MM-DD)"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    # No specific authentication required for this, public or any authenticated user can view.
    # current_user: Optional[User] = Depends(deps.get_current_user) # Optional: if you want to log who is viewing
):
    # Consider adding a service function to check if tenant_id is valid/active before fetching slots.
    slots = timeslot_service.get_timeslots_by_tenant(
        db, tenant_id=tenant_id, skip=skip, limit=limit,
        date_from=date_from, date_to=date_to,
        only_available=True, is_active=True # Crucial: only active and available slots
    )
    return slots

# Endpoints for Tenant Admins to manage all slots for their tenant
@router.get("/", response_model=List[PickupTimeSlotResponse])
def read_all_timeslots_for_admin(
    skip: int = 0,
    limit: int = 100,
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    tenant_id_to_filter: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
        # As with create, super_admin should use a tenant-specific path or provide tenant_id as query param.
        # For this example, let's assume super_admin must use a query param if this endpoint is to be used.
        # tenant_id_query: Optional[int] = Query(None, alias="targetTenantId")
        # if not tenant_id_query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin must specify tenant_id via a query parameter (e.g. ?targetTenantId=X) to list timeslots, or use a tenant-specific path.")
        # effective_tenant_id = tenant_id_query
    else: # Must be tenant_admin
        if not current_user.tenant_id: # Should not happen due to dependency
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
        tenant_id_to_filter = current_user.tenant_id


    slots = timeslot_service.get_timeslots_by_tenant(
        db, tenant_id=tenant_id_to_filter, skip=skip, limit=limit, # type: ignore
        date_from=date_from, date_to=date_to, is_active=is_active, only_available=False # Admin sees all (not just available)
    )
    return slots

@router.get("/{timeslot_id}", response_model=PickupTimeSlotResponse)
def read_timeslot_by_id_for_admin(
    timeslot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    tenant_id_to_filter: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin timeslot view needs tenant context (e.g. /admin/tenants/{id}/timeslots/{slot_id}) or global slot ID if applicable.")
    else: # Must be tenant_admin
        if not current_user.tenant_id:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
        tenant_id_to_filter = current_user.tenant_id

    db_timeslot = timeslot_service.get_timeslot_by_id(db, timeslot_id=timeslot_id, tenant_id=tenant_id_to_filter) # type: ignore
    if db_timeslot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pickup time slot not found for your tenant")
    return db_timeslot

@router.put("/{timeslot_id}", response_model=PickupTimeSlotResponse)
def update_existing_timeslot(
    timeslot_id: int,
    timeslot_in: PickupTimeSlotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    tenant_id_to_filter: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin timeslot update needs tenant context.")
    else: # Must be tenant_admin
        if not current_user.tenant_id:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
        tenant_id_to_filter = current_user.tenant_id

    db_timeslot = timeslot_service.get_timeslot_by_id(db, timeslot_id=timeslot_id, tenant_id=tenant_id_to_filter) # type: ignore
    if db_timeslot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pickup time slot not found for your tenant")

    return timeslot_service.update_timeslot(db=db, db_timeslot=db_timeslot, timeslot_in=timeslot_in)

@router.delete("/{timeslot_id}", response_model=PickupTimeSlotResponse)
def delete_existing_timeslot(
    timeslot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    tenant_id_to_filter: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin timeslot deletion needs tenant context.")
    else: # Must be tenant_admin
        if not current_user.tenant_id:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
        tenant_id_to_filter = current_user.tenant_id

    db_timeslot = timeslot_service.get_timeslot_by_id(db, timeslot_id=timeslot_id, tenant_id=tenant_id_to_filter) # type: ignore
    if db_timeslot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pickup time slot not found for your tenant")

    return timeslot_service.delete_timeslot(db=db, db_timeslot=db_timeslot)
