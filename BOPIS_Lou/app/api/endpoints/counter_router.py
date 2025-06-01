from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.models.sql_models import User, Order
from app.models.sql_models import UserRole as DBUserRoleEnum
from app.models.sql_models import OrderStatus as DBOrderStatusEnum
from app.models.sql_models import LaneStatus as DBLaneStatusEnum

from app.schemas.counter_schemas import (
    CounterOrderSummaryResponse,
    CounterAssignOrderToLaneRequest,
    # OrderVerificationDataResponse is used in order_router
)
from app.schemas.order_schemas import OrderResponse # For return type of assign to lane
from app.services import order_service, lane_service # Import lane_service
from app.api import deps

router = APIRouter()

def get_counter_user(current_user: User = Depends(deps.get_current_user)) -> User:
    # Tenant admins and super admins can also perform counter actions for now
    if current_user.role not in [DBUserRoleEnum.counter, DBUserRoleEnum.tenant_admin, DBUserRoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not have counter privileges.")
    if not current_user.tenant_id and current_user.role != DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff must be associated with a tenant.")
    return current_user

@router.get("/orders", response_model=List[CounterOrderSummaryResponse])
def list_orders_for_counter_staff(
    lane_id: Optional[int] = Query(None, description="Filter by specific lane ID"),
    unassigned: Optional[bool] = Query(False, description="Filter for unassigned orders"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    counter_staff: User = Depends(get_counter_user)
):
    tenant_id_context = counter_staff.tenant_id
    if counter_staff.role == DBUserRoleEnum.super_admin:
        # Super admin needs tenant_id as query param if not using a tenant-specific path
        # For this specific router, let's assume super_admin needs to specify tenant context.
        # This could be via a query parameter like ?targetTenantId=...
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin must specify tenant context to view counter orders for a specific tenant.")

    if not tenant_id_context: # Should be true for counter/tenant_admin due to get_counter_user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context not found for user.")

    orders = order_service.list_orders_for_counter(
        db, counter_user=counter_staff, skip=skip, limit=limit,
        lane_id=lane_id, unassigned=unassigned
    )
    # OrderResponse is inherited by CounterOrderSummaryResponse, direct return should be fine.
    return orders

@router.post("/orders/{order_id}/assign-to-lane", response_model=OrderResponse)
def counter_assigns_order_to_lane(
    order_id: int,
    assignment_request: CounterAssignOrderToLaneRequest,
    db: Session = Depends(get_db),
    counter_staff: User = Depends(get_counter_user)
):
    tenant_id_context = counter_staff.tenant_id
    if counter_staff.role == DBUserRoleEnum.super_admin:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin action requires specific tenant context for assigning order to lane.")
    if not tenant_id_context:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context not found for user.")

    # Fetch order details, ensuring it's in the right state and tenant
    order = order_service.get_order_details(db, order_id=order_id, user_id_for_auth=counter_staff.id, user_role_for_auth=counter_staff.role, tenant_id_for_auth=tenant_id_context)
    if not order: # Service raises 404/403, this is a safeguard
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or not accessible.")
    if order.status != DBOrderStatusEnum.READY_FOR_PICKUP:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order is not ready for pickup. Current status: {order.status.value}") # type: ignore
    if order.assigned_lane_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order is already assigned to lane {order.assigned_lane_id}.")


    # Fetch lane details
    lane = lane_service.get_lane_by_id(db, lane_id=assignment_request.lane_id, tenant_id=tenant_id_context)
    if not lane:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found.")
    if lane.status != DBLaneStatusEnum.OPEN:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Lane is not OPEN. Current status: {lane.status.value}") # type: ignore
    if lane.current_order_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Lane is already busy with order {lane.current_order_id}.")

    # Service function handles setting order.assigned_lane_id and lane.current_order_id & status
    lane_service.assign_order_to_lane(db, lane=lane, order=order, counter_user=counter_staff)

    # Return the updated order details, which should now reflect the assigned_lane_id
    # and potentially other related changes if the lane object in order response is populated.
    updated_order = order_service.get_order_details(db, order_id=order_id, user_id_for_auth=counter_staff.id, user_role_for_auth=counter_staff.role, tenant_id_for_auth=tenant_id_context)
    return updated_order
