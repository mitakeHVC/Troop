from fastapi import APIRouter, Depends, HTTPException, status, Query # Added Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models.sql_models import User, Lane, StaffAssignment # Added StaffAssignment
from app.models.sql_models import UserRole as DBUserRoleEnum # For role comparison
from app.schemas.lane_schemas import (
    LaneCreate, LaneResponse, LaneUpdate, LaneStatusUpdateRequest,
    StaffAssignmentToLaneCreate, StaffAssignmentResponse,
    LaneStatusEnum as PydanticLaneStatusEnum # Import Pydantic enum
)
from app.services import lane_service
from app.api import deps

router = APIRouter()

# Admin: Manage Lanes (CRUD)
@router.post("/", response_model=LaneResponse, status_code=status.HTTP_201_CREATED)
def create_new_lane_admin(
    lane_in: LaneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    tenant_id_for_creation: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admins must operate via a tenant-specific path (e.g. /tenants/{id}/lanes) to create lanes.")

    if not current_user.tenant_id: # Should be set for tenant_admin due to dependency
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
    tenant_id_for_creation = current_user.tenant_id
    return lane_service.create_lane(db=db, lane_in=lane_in, tenant_id=tenant_id_for_creation)

@router.get("/", response_model=List[LaneResponse])
def list_lanes_admin_or_staff(
    status_filter: Optional[PydanticLaneStatusEnum] = Query(None, alias="status"),
    target_tenant_id: Optional[int] = Query(None, description="Super_admin can use this to specify tenant context."), # Added for SA
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user) # Allow any authenticated staff to see lanes
):
    effective_tenant_id: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
        if target_tenant_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin must specify 'target_tenant_id' query parameter to list lanes.")
        effective_tenant_id = target_tenant_id
    elif current_user.tenant_id: # For tenant_admin, picker, counter
        if target_tenant_id and target_tenant_id != current_user.tenant_id:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view lanes for the specified tenant.")
        effective_tenant_id = current_user.tenant_id
    else: # Should not happen if user has role that requires tenant_id and dependency is correct
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not associated with a tenant or invalid context.")

    lanes = lane_service.get_lanes_by_tenant(db, tenant_id=effective_tenant_id, status_filter=status_filter)
    return lanes

@router.get("/{lane_id}", response_model=LaneResponse)
def get_lane_details_admin_or_staff(
    lane_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    tenant_id_for_filter: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admins must query lanes via a specific tenant context.")
    if not current_user.tenant_id:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not associated with a tenant.")
    tenant_id_for_filter = current_user.tenant_id

    db_lane = lane_service.get_lane_by_id(db, lane_id=lane_id, tenant_id=tenant_id_for_filter)
    if not db_lane:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found in your tenant")
    return db_lane

@router.put("/{lane_id}", response_model=LaneResponse)
def update_lane_admin(
    lane_id: int,
    lane_in: LaneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    tenant_id_for_operation: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admins must operate on a specific tenant context.")
    if not current_user.tenant_id:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
    tenant_id_for_operation = current_user.tenant_id

    db_lane = lane_service.get_lane_by_id(db, lane_id=lane_id, tenant_id=tenant_id_for_operation)
    if not db_lane:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found")
    return lane_service.update_lane_details(db=db, db_lane=db_lane, lane_in=lane_in)

@router.delete("/{lane_id}", response_model=LaneResponse)
def delete_lane_admin(
    lane_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    tenant_id_for_operation: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admins must operate on a specific tenant context.")
    if not current_user.tenant_id:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
    tenant_id_for_operation = current_user.tenant_id

    db_lane = lane_service.get_lane_by_id(db, lane_id=lane_id, tenant_id=tenant_id_for_operation)
    if not db_lane:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found")
    return lane_service.delete_lane(db=db, db_lane=db_lane)

# Counter Staff: Update own assigned lane status
@router.patch("/{lane_id}/status", response_model=LaneResponse)
def update_lane_status_staff_or_admin( # Renamed to reflect admin can also use it
    lane_id: int,
    status_in: LaneStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    tenant_id = current_user.tenant_id
    if not tenant_id: # All relevant roles (counter, tenant_admin, super_admin if allowed) need tenant context
        # Super_admin would need a way to specify tenant_id if they use this endpoint.
        # For now, if tenant_id is None on current_user, it's an issue (unless they are SA and we add specific logic).
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not associated with a tenant or tenant context not clear.")

    db_lane = lane_service.get_lane_by_id(db, lane_id=lane_id, tenant_id=tenant_id)
    if not db_lane:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found in your tenant")

    if current_user.role == DBUserRoleEnum.counter:
        is_assigned_and_active = db.query(StaffAssignment).filter(
            StaffAssignment.lane_id == lane_id,
            StaffAssignment.user_id == current_user.id,
            StaffAssignment.is_active == True
        ).first()
        if not is_assigned_and_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Counter staff not actively assigned to this lane.")
    elif current_user.role not in [DBUserRoleEnum.tenant_admin, DBUserRoleEnum.super_admin]: # tenant_admin/super_admin can also change status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not have permission to change lane status.")

    return lane_service.update_lane_status(db=db, db_lane=db_lane, new_status=status_in.status)

# Admin: Assign/Unassign Staff from Lane
@router.post("/{lane_id}/staff-assignments", response_model=StaffAssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_staff_to_lane_admin(
    lane_id: int,
    assignment_in: StaffAssignmentToLaneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    tenant_id_for_operation: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admins must operate on a specific tenant context.")
    if not current_user.tenant_id:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
    tenant_id_for_operation = current_user.tenant_id

    db_lane = lane_service.get_lane_by_id(db, lane_id=lane_id, tenant_id=tenant_id_for_operation)
    if not db_lane:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found")

    return lane_service.assign_staff_to_lane(db=db, lane=db_lane, user_id=assignment_in.user_id, tenant_id=tenant_id_for_operation)

@router.delete("/{lane_id}/staff-assignments/{assignment_id}", response_model=StaffAssignmentResponse)
def unassign_staff_from_lane_admin(
    lane_id: int,
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    tenant_id_for_operation: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admins must operate on a specific tenant context.")
    if not current_user.tenant_id:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
    tenant_id_for_operation = current_user.tenant_id

    return lane_service.unassign_staff_from_lane(db=db, assignment_id=assignment_id, lane_id=lane_id, tenant_id=tenant_id_for_operation)

@router.get("/{lane_id}/staff-assignments", response_model=List[StaffAssignmentResponse])
def get_lane_staff_assignments_admin(
    lane_id: int,
    only_active: bool = Query(True, alias="active"),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    tenant_id_for_operation: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admins must operate on a specific tenant context.")
    if not current_user.tenant_id:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin not associated with a tenant.")
    tenant_id_for_operation = current_user.tenant_id

    # Verify lane belongs to tenant first
    db_lane = lane_service.get_lane_by_id(db, lane_id=lane_id, tenant_id=tenant_id_for_operation)
    if not db_lane:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found for this tenant.")

    return lane_service.get_staff_assignments_for_lane(db, lane_id=lane_id, tenant_id=tenant_id_for_operation, only_active=only_active)
