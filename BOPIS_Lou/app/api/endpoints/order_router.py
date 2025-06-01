from fastapi import APIRouter, Depends, HTTPException, status, Path, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.models.sql_models import User, Order as DBOrder, OrderItem as DBOrderItem
from app.models.sql_models import UserRole as DBUserRoleEnum
from app.models.sql_models import OrderStatus as DBOrderStatusEnum
from app.schemas.order_schemas import (
    OrderResponse, OrderItemResponse,
    CartItemCreateRequest, CartItemUpdateRequest, CheckoutRequestSchema,
    OrderPickupTokenVerificationRequest # Added for verify endpoint
)
from app.schemas.counter_schemas import OrderVerificationDataResponse, CounterOrderCompleteRequest # Added for complete endpoint
from app.services import order_service, product_service, lane_service # Added lane_service
from app.api import deps

router = APIRouter()

# Helper function to get counter user (can be moved to deps if used elsewhere)
def get_counter_user_for_order_ops(current_user: User = Depends(deps.get_current_user)) -> User:
    if current_user.role not in [DBUserRoleEnum.counter, DBUserRoleEnum.tenant_admin, DBUserRoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not have counter or admin privileges for this operation.")
    if not current_user.tenant_id and current_user.role != DBUserRoleEnum.super_admin: # Counters/TenantAdmins must have tenant_id
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff must be associated with a tenant.")
    return current_user

# --- Cart Operations ---
@router.get("/cart", response_model=OrderResponse)
def get_current_user_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    if not current_user.tenant_id and current_user.role != DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not associated with a tenant for cart operations.")
    if current_user.role == DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin cannot have a personal shopping cart.")

    cart = order_service.get_cart_by_user_id(db, user_id=current_user.id, tenant_id=current_user.tenant_id, create_if_not_exists=True) # type: ignore
    if not cart:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve or create cart.")
    return cart

@router.post("/cart/items", response_model=OrderResponse)
def add_item_to_current_user_cart(
    item_in: CartItemCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    if not current_user.tenant_id and current_user.role != DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not associated with a tenant.")
    if current_user.role == DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin cannot add items to a personal cart.")

    product = product_service.get_product_by_id(db, product_id=item_in.product_id, tenant_id=current_user.tenant_id) # type: ignore
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product not found in tenant {current_user.tenant_id}.")

    cart = order_service.get_cart_by_user_id(db, user_id=current_user.id, tenant_id=current_user.tenant_id, create_if_not_exists=True) # type: ignore
    if not cart:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve or create cart.")

    updated_cart = order_service.add_item_to_cart(db, cart_order=cart, product_id=item_in.product_id, quantity=item_in.quantity)
    return updated_cart

@router.put("/cart/items/{item_id}", response_model=OrderResponse)
def update_cart_item_in_current_user_cart(
    item_id: int,
    item_update: CartItemUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    if not current_user.tenant_id and current_user.role != DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not associated with a tenant.")
    if current_user.role == DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin cannot manage a personal cart.")

    cart = order_service.get_cart_by_user_id(db, user_id=current_user.id, tenant_id=current_user.tenant_id) # type: ignore
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active cart not found.")

    updated_cart = order_service.update_cart_item_quantity(db, cart_order=cart, order_item_id=item_id, new_quantity=item_update.quantity)
    return updated_cart

@router.delete("/cart/items/{item_id}", response_model=OrderResponse)
def remove_cart_item_from_current_user_cart(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    if not current_user.tenant_id and current_user.role != DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not associated with a tenant.")
    if current_user.role == DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin cannot manage a personal cart.")

    cart = order_service.get_cart_by_user_id(db, user_id=current_user.id, tenant_id=current_user.tenant_id) # type: ignore
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active cart not found.")

    updated_cart = order_service.remove_cart_item(db, cart_order=cart, order_item_id=item_id)
    return updated_cart

# --- Checkout ---
@router.post("/{cart_order_id}/checkout", response_model=OrderResponse)
def checkout_user_cart(
    cart_order_id: int,
    checkout_details: CheckoutRequestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    cart_order_to_checkout = db.query(DBOrder).filter(
        DBOrder.id == cart_order_id,
        DBOrder.user_id == current_user.id, # Ensure current user owns the cart
        DBOrder.status == DBOrderStatusEnum.CART
    ).first()

    if not cart_order_to_checkout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found, not owned by user, or not in 'CART' status.")

    try:
        confirmed_order = order_service.checkout_cart(db, cart_order=cart_order_to_checkout, checkout_details=checkout_details)
        return confirmed_order
    except HTTPException as e:
        raise e
    except Exception as e:
        # Log error e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Checkout failed due to an unexpected error.")


# --- Order Viewing ---
@router.get("/", response_model=List[OrderResponse])
def list_orders( # Renamed from list_my_orders for clarity
    skip: int = 0,
    limit: int = 100,
    tenant_id_filter: Optional[int] = Query(None, alias="tenantId"), # For super_admin to filter by tenant
    status_filter: Optional[str] = Query(None, alias="status"), # Example filter
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    # Service layer (list_orders_for_user) handles permission logic based on user role
    orders = order_service.list_orders_for_user(db, user=current_user, skip=skip, limit=limit) # Pass filters to service if implemented
    return orders

@router.get("/{order_id}", response_model=OrderResponse)
def get_order_details( # Renamed from get_my_order_details
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    # Service layer handles permission logic
    order = order_service.get_order_details(db, order_id=order_id, user_id_for_auth=current_user.id, user_role_for_auth=current_user.role, tenant_id_for_auth=current_user.tenant_id) # type: ignore
    return order


# --- Order Verification & Completion (for Counter Staff) ---
@router.post("/verify-pickup", response_model=OrderVerificationDataResponse)
def verify_order_by_pickup_token(
    token_request: OrderPickupTokenVerificationRequest,
    db: Session = Depends(get_db),
    counter_staff: User = Depends(get_counter_user_for_order_ops) # Ensures counter/admin role
):
    if not counter_staff.tenant_id and counter_staff.role != DBUserRoleEnum.super_admin:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff must be associated with a tenant.")

    # If super_admin, they would need to specify tenant_id context for the token.
    # For now, assume counter_staff or tenant_admin use this within their tenant.
    tenant_id_context = counter_staff.tenant_id
    if counter_staff.role == DBUserRoleEnum.super_admin:
        # This endpoint is problematic for SA without a tenant_id in request or if tokens are not globally unique.
        # Assuming tokens are unique within a tenant or globally. If globally, tenant_id not needed for lookup.
        # If unique per tenant, SA needs to provide tenant_id.
        # For now, let's assume service handles it or SA needs a different endpoint.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin token verification requires tenant context if tokens are not global.")


    order = order_service.get_order_by_pickup_token(db, token_request.pickup_token, tenant_id=tenant_id_context) # type: ignore
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired pickup token for this tenant.")

    if order.status != DBOrderStatusEnum.READY_FOR_PICKUP:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order is not ready for pickup. Current status: {order.status.value}") # type: ignore

    return order_service.prepare_order_verification_data(db, order=order)


@router.post("/{order_id}/complete-pickup", response_model=OrderResponse)
def complete_order_pickup(
    order_id: int,
    completion_request: CounterOrderCompleteRequest, # Assuming this is the Pydantic model name
    db: Session = Depends(get_db),
    counter_staff: User = Depends(get_counter_user_for_order_ops)
):
    tenant_id_context = counter_staff.tenant_id
    if counter_staff.role == DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin action requires specific tenant context.")
    if not tenant_id_context:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff must be associated with a tenant.")

    # Fetch order, service layer will ensure it belongs to the right tenant for the staff.
    order_to_complete = order_service.get_order_details(db, order_id=order_id, user_id_for_auth=counter_staff.id, user_role_for_auth=counter_staff.role, tenant_id_for_auth=tenant_id_context)
    if not order_to_complete: # Safeguard
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or not accessible.")

    # Pass the lane_service module to the order_service function
    updated_order = order_service.counter_complete_order_pickup(
        db,
        order=order_to_complete,
        counter_user=counter_staff,
        request_data=completion_request,
        lane_service_module=lane_service # Pass the imported module
    )
    return updated_order
