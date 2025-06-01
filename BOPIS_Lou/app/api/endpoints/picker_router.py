from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional # Added Optional
from app.db.session import get_db
from app.models.sql_models import User, Order # Removed DBUserRoleEnum as it's used via User model's role attribute
from app.models.sql_models import UserRole as DBUserRoleEnum # Explicit import for clarity
from app.schemas.picker_schemas import PickerOrderSummaryResponse, PickerOrderDetailsResponse, PickerReadyForPickupRequest
from app.schemas.order_schemas import OrderStatusEnum # For casting status from DB to Pydantic
from app.services import order_service
from app.api import deps

router = APIRouter()

def get_picker_user(current_user: User = Depends(deps.get_current_user)) -> User:
    # Tenant admins and super admins can also perform picker actions for now
    if current_user.role not in [DBUserRoleEnum.picker, DBUserRoleEnum.tenant_admin, DBUserRoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not have picker privileges.")
    if not current_user.tenant_id and current_user.role != DBUserRoleEnum.super_admin: # Pickers and Tenant Admins must have a tenant_id
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role requires association with a tenant.")
    return current_user

@router.get("/orders", response_model=List[PickerOrderSummaryResponse])
def list_orders_for_current_picker(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    picker: User = Depends(get_picker_user)
):
    if picker.role == DBUserRoleEnum.super_admin:
        # Super_admin needs to act within a tenant context. This endpoint is for assigned pickers/admins of a tenant.
        # A different endpoint or query parameter would be needed for super_admin to specify tenant.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin must specify tenant context to view picker orders. This endpoint is for tenant-associated pickers/admins.")

    orders = order_service.list_orders_for_picker(db, picker_user=picker, skip=skip, limit=limit)

    response_orders = []
    for order in orders:
        item_count = sum(item.quantity for item in order.order_items if item.quantity is not None) # Sum quantities
        response_orders.append(PickerOrderSummaryResponse(
            id=order.id,
            status=OrderStatusEnum(order.status.value), # Cast DB enum to Pydantic enum
            pickup_slot_id=order.pickup_slot_id,
            item_count=item_count,
            created_at=order.created_at, # type: ignore
            updated_at=order.updated_at  # type: ignore
        ))
    return response_orders


@router.get("/orders/{order_id}", response_model=PickerOrderDetailsResponse)
def get_order_details_for_picker(
    order_id: int,
    db: Session = Depends(get_db),
    picker: User = Depends(get_picker_user)
):
    tenant_id_context = picker.tenant_id
    if picker.role == DBUserRoleEnum.super_admin:
        # If super_admin is to use this, they must specify tenant_id.
        # For now, this endpoint is primarily for pickers within their tenant.
        # The order_service.get_order_details will handle actual permissions.
        # However, a SA without tenant_id from token cannot proceed here.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin order view requires specific tenant context for this picker endpoint.")

    # The service function get_order_details already checks user's access rights.
    order = order_service.get_order_details(db, order_id=order_id, user_id_for_auth=picker.id, user_role_for_auth=picker.role, tenant_id_for_auth=tenant_id_context)
    # No need to double check tenant_id here as service layer does it based on role.
    if not order: # Should be caught by service layer's HTTPException, but as safeguard
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or not accessible.")
    return order


@router.post("/orders/{order_id}/start-picking", response_model=PickerOrderDetailsResponse)
def picker_starts_processing_order(
    order_id: int,
    db: Session = Depends(get_db),
    picker: User = Depends(get_picker_user)
):
    tenant_id_context = picker.tenant_id
    if picker.role == DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin action requires specific tenant context for this picker endpoint.")

    # Fetch order using the generic get_order_details which checks permissions
    order_to_start = order_service.get_order_details(db, order_id=order_id, user_id_for_auth=picker.id, user_role_for_auth=picker.role, tenant_id_for_auth=tenant_id_context)
    if not order_to_start: # Safeguard
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or not accessible.")

    updated_order = order_service.picker_start_order_processing(db, order=order_to_start, picker_user=picker)
    return updated_order


@router.post("/orders/{order_id}/ready-for-pickup", response_model=PickerOrderDetailsResponse)
def picker_marks_order_as_ready(
    order_id: int,
    request_data: PickerReadyForPickupRequest,
    db: Session = Depends(get_db),
    picker: User = Depends(get_picker_user)
):
    tenant_id_context = picker.tenant_id
    if picker.role == DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin action requires specific tenant context for this picker endpoint.")

    order_to_mark = order_service.get_order_details(db, order_id=order_id, user_id_for_auth=picker.id, user_role_for_auth=picker.role, tenant_id_for_auth=tenant_id_context)
    if not order_to_mark: # Safeguard
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or not accessible.")

    updated_order = order_service.picker_mark_order_ready(db, order=order_to_mark, picker_user=picker, request_data=request_data)
    return updated_order
