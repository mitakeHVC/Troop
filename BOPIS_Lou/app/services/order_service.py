from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func as sql_func, or_
from typing import List, Optional, Any
import uuid
import random
import decimal # Added decimal import
from fastapi import HTTPException, status

from app.models.sql_models import (
    Order, OrderItem, Product, PickupTimeSlot, User, Notification, Lane,
    OrderStatus as DBOrderStatusEnum,
    OrderType as DBOrderTypeEnum,
    PaymentStatus as DBPaymentStatusEnum,
    UserRole as DBUserRoleEnum
)
from app.schemas.order_schemas import (
    OrderItemCreate, OrderItemUpdate, CheckoutRequestSchema, OrderCreate, OrderStatusEnum # Added OrderStatusEnum
)
from app.schemas.picker_schemas import PickerReadyForPickupRequest
from app.schemas.counter_schemas import OrderVerificationDataResponse, CounterOrderCompleteRequest
from app.schemas.pos_schemas import POSOrderCreateRequest # Added for POS

# Import service dependencies
from app.services import product_service, timeslot_service
# lane_service will be imported where needed to avoid circular dependency


def _recalculate_cart_total(db: Session, cart_order: Order) -> None:
    if not cart_order:
        return
    total = sum(item.price_at_purchase * item.quantity for item in cart_order.order_items if item.price_at_purchase is not None and item.quantity is not None)
    cart_order.total_amount = total # type: ignore
    db.add(cart_order)


def get_cart_by_user_id(db: Session, user_id: int, tenant_id: int, create_if_not_exists: bool = False) -> Optional[Order]:
    cart = db.query(Order).options(selectinload(Order.order_items).selectinload(OrderItem.product)).filter(
        Order.user_id == user_id,
        Order.tenant_id == tenant_id,
        Order.status == DBOrderStatusEnum.CART
    ).first()

    if not cart and create_if_not_exists:
        # Ensure OrderCreate is correctly initialized; it expects order_type as Pydantic enum
        order_data = OrderCreate(user_id=user_id, tenant_id=tenant_id, order_type=OrderStatusEnum.CART) # type: ignore
        cart = Order(
            user_id=order_data.user_id,
            tenant_id=order_data.tenant_id,
            order_type=DBOrderTypeEnum[order_data.order_type.value], # Use .value for Pydantic enum
            status=DBOrderStatusEnum.CART,
            payment_status=DBPaymentStatusEnum.UNPAID,
            total_amount=decimal.Decimal("0.00") # Use decimal.Decimal
        )
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart

def add_item_to_cart(db: Session, cart_order: Order, product_id: int, quantity: int) -> Order:
    # ... (previous implementation, ensure decimal for price_at_purchase)
    if cart_order.status != DBOrderStatusEnum.CART:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not a cart.")

    product = product_service.get_product_by_id(db, product_id=product_id, tenant_id=cart_order.tenant_id) # type: ignore
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    if product.stock_quantity < quantity: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Not enough stock for {product.name}. Available: {product.stock_quantity}")

    existing_item = db.query(OrderItem).filter(
        OrderItem.order_id == cart_order.id,
        OrderItem.product_id == product_id
    ).first()

    if existing_item:
        new_total_quantity = existing_item.quantity + quantity # type: ignore
        if product.stock_quantity < new_total_quantity: # type: ignore
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Not enough stock for {product.name} for total quantity {new_total_quantity}. Available: {product.stock_quantity}")
        existing_item.quantity = new_total_quantity # type: ignore
        db.add(existing_item)
    else:
        new_item = OrderItem(
            order_id=cart_order.id,
            product_id=product_id,
            quantity=quantity,
            price_at_purchase=product.price # type: ignore Ensure this is decimal
        )
        db.add(new_item)
        cart_order.order_items.append(new_item)

    _recalculate_cart_total(db, cart_order)
    db.commit()
    db.refresh(cart_order)
    cart_order = db.query(Order).options(selectinload(Order.order_items).selectinload(OrderItem.product)).filter(Order.id == cart_order.id).first()
    return cart_order # type: ignore


def update_cart_item_quantity(db: Session, cart_order: Order, order_item_id: int, new_quantity: int) -> Order:
    # ... (previous implementation)
    if cart_order.status != DBOrderStatusEnum.CART:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not a cart.")

    item_to_update = db.query(OrderItem).filter(
        OrderItem.id == order_item_id,
        OrderItem.order_id == cart_order.id
    ).first()

    if not item_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found.")

    # product = product_service.get_product_by_id(db, product_id=item_to_update.product_id, tenant_id=cart_order.tenant_id) # type: ignore
    # if not product:
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product associated with item not found.")
    # Stock check at checkout is more critical for final validation.
    # if product.stock_quantity < new_quantity:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Not enough stock for {product.name}. Available: {product.stock_quantity}")

    item_to_update.quantity = new_quantity # type: ignore
    db.add(item_to_update)
    _recalculate_cart_total(db, cart_order)
    db.commit()
    db.refresh(cart_order)
    cart_order = db.query(Order).options(selectinload(Order.order_items).selectinload(OrderItem.product)).filter(Order.id == cart_order.id).first()
    return cart_order # type: ignore


def remove_cart_item(db: Session, cart_order: Order, order_item_id: int) -> Order:
    # ... (previous implementation) ...
    if cart_order.status != DBOrderStatusEnum.CART:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not a cart.")

    item_to_remove = next((item for item in cart_order.order_items if item.id == order_item_id), None)

    if not item_to_remove:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found.")

    cart_order.order_items.remove(item_to_remove) # Important for _recalculate_cart_total if it uses the collection
    db.delete(item_to_remove)
    _recalculate_cart_total(db, cart_order)
    db.commit()
    # db.refresh(cart_order) # Might not be strictly necessary if only items changed and total recalculated
    # Re-fetch to ensure clean state and eager loads
    cart_order = db.query(Order).options(selectinload(Order.order_items).selectinload(OrderItem.product)).filter(Order.id == cart_order.id).first()
    return cart_order # type: ignore

def checkout_cart(db: Session, cart_order: Order, checkout_details: CheckoutRequestSchema) -> Order:
    # ... (implementation from previous step, ensure it's complete and correct) ...
    if cart_order.status != DBOrderStatusEnum.CART:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only an active cart can be checked out.")
    if not cart_order.order_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot checkout an empty cart.")

    slot = timeslot_service.get_timeslot_by_id(db, timeslot_id=checkout_details.pickup_slot_id, tenant_id=cart_order.tenant_id) # type: ignore
    if not slot or not slot.is_active or slot.current_orders >= slot.capacity: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected pickup slot is not available or full.")

    for item in cart_order.order_items:
        product = product_service.get_product_by_id(db, product_id=item.product_id, tenant_id=cart_order.tenant_id) # type: ignore
        if not product or product.stock_quantity < item.quantity: # type: ignore
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product {product.name if product else item.product_id} out of stock or insufficient quantity.") # type: ignore

    for item in cart_order.order_items:
        # It's safer to call a dedicated product service function here
        # product_service.decrement_stock(db, product_id=item.product_id, quantity=item.quantity, tenant_id=cart_order.tenant_id)
        product_to_update = db.query(Product).filter(Product.id == item.product_id, Product.tenant_id == cart_order.tenant_id).first() # type: ignore
        if product_to_update:
            product_to_update.stock_quantity -= item.quantity # type: ignore
            product_to_update.version += 1 # type: ignore
            db.add(product_to_update)

    cart_order.status = DBOrderStatusEnum.ORDER_CONFIRMED # type: ignore
    cart_order.payment_status = DBPaymentStatusEnum.PAID # type: ignore
    cart_order.pickup_slot_id = checkout_details.pickup_slot_id # type: ignore
    cart_order.pickup_token = str(uuid.uuid4()) # type: ignore

    if cart_order.order_items:
        cart_order.identity_verification_product_id = random.choice(cart_order.order_items).product_id # type: ignore

    timeslot_service.increment_slot_order_count(db, timeslot_id=checkout_details.pickup_slot_id, tenant_id=cart_order.tenant_id) # type: ignore

    _recalculate_cart_total(db, cart_order)
    db.add(cart_order)
    db.commit()
    db.refresh(cart_order)
    refreshed_order = db.query(Order).options(
        selectinload(Order.order_items).selectinload(OrderItem.product),
        selectinload(Order.customer),
        selectinload(Order.pickup_slot)
    ).filter(Order.id == cart_order.id).first()
    return refreshed_order # type: ignore

def get_order_details(db: Session, order_id: int, user_id_for_auth: int, user_role_for_auth: DBUserRoleEnum, tenant_id_for_auth: Optional[int]) -> Optional[Order]:
    # ... (implementation from previous step) ...
    query = db.query(Order).options(
        selectinload(Order.order_items).selectinload(OrderItem.product).joinedload(Product.tenant),
        selectinload(Order.customer),
        selectinload(Order.pickup_slot),
        selectinload(Order.assigned_lane).selectinload(Lane.staff_assignments).selectinload(StaffAssignment.user) # Example of deeper load if needed
    ).filter(Order.id == order_id)

    # Fetch minimal data for permission check first to avoid unnecessary joins if user is unauthorized
    order_owner_info = db.query(Order.user_id, Order.tenant_id).filter(Order.id == order_id).first() # type: ignore
    if not order_owner_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    if user_role_for_auth == DBUserRoleEnum.super_admin:
        pass
    elif user_role_for_auth in [DBUserRoleEnum.tenant_admin, DBUserRoleEnum.picker, DBUserRoleEnum.counter]:
        if tenant_id_for_auth is None or order_owner_info.tenant_id != tenant_id_for_auth:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this order.")
    else: # Customer
        if order_owner_info.user_id != user_id_for_auth:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this order.")

    return query.first()


def list_orders_for_user(db: Session, user: User, skip: int = 0, limit: int = 100) -> List[Order]:
    # ... (implementation from previous step) ...
    query = db.query(Order).options(
        selectinload(Order.order_items).selectinload(OrderItem.product),
        selectinload(Order.pickup_slot)
    ) # Add other options as needed for list view
    if user.role == DBUserRoleEnum.super_admin:
        # Consider adding tenant_id filter for SA if performance is an issue for "all orders"
        pass
    elif user.role in [DBUserRoleEnum.tenant_admin, DBUserRoleEnum.picker, DBUserRoleEnum.counter]:
        if not user.tenant_id:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context required for staff/admin.")
        query = query.filter(Order.tenant_id == user.tenant_id)
    else: # Customer
        query = query.filter(Order.user_id == user.id)

    return query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all() # type: ignore

# --- Picker Service Functions ---
def list_orders_for_picker(db: Session, picker_user: User, skip: int = 0, limit: int = 100) -> List[Order]:
    # ... (implementation from previous step) ...
    if not picker_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Picker not associated with a tenant.")

    query = db.query(Order).filter(
        Order.tenant_id == picker_user.tenant_id,
        or_(Order.status == DBOrderStatusEnum.ORDER_CONFIRMED, Order.status == DBOrderStatusEnum.PROCESSING)
    ).options(selectinload(Order.order_items))

    return query.order_by(Order.created_at).offset(skip).limit(limit).all()

def picker_start_order_processing(db: Session, order: Order, picker_user: User) -> Order:
    # ... (implementation from previous step) ...
    if order.tenant_id != picker_user.tenant_id: # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this tenant's order")
    if order.status != DBOrderStatusEnum.ORDER_CONFIRMED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order cannot be started; current status: {order.status.value}")

    order.status = DBOrderStatusEnum.PROCESSING # type: ignore
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

def picker_mark_order_ready(db: Session, order: Order, picker_user: User, request_data: PickerReadyForPickupRequest) -> Order:
    # ... (implementation from previous step) ...
    if order.tenant_id != picker_user.tenant_id: # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this tenant's order")
    if order.status != DBOrderStatusEnum.PROCESSING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order cannot be marked ready; current status: {order.status.value}")

    order.status = DBOrderStatusEnum.READY_FOR_PICKUP # type: ignore

    db.add(order)

    users_to_notify = db.query(User).filter(
        User.tenant_id == order.tenant_id, # type: ignore
        User.is_active == True,
        or_(User.role == DBUserRoleEnum.tenant_admin, User.role == DBUserRoleEnum.counter)
    ).all()

    for user_to_notify in users_to_notify:
        notification_message = f"Order {order.id} (Token: {order.pickup_token}) is now READY FOR PICKUP."
        if request_data.notes:
            notification_message += f" Picker notes: {request_data.notes}"

        db_notification = Notification(
            user_id=user_to_notify.id,
            tenant_id=order.tenant_id, # type: ignore
            message=notification_message,
            related_order_id=order.id # type: ignore
        )
        db.add(db_notification)

    db.commit()
    db.refresh(order)
    return order

# --- Counter Service Functions ---
def get_order_by_pickup_token(db: Session, pickup_token: str, tenant_id: int) -> Optional[Order]:
    # ... (implementation from previous step) ...
    return db.query(Order).filter(
        Order.pickup_token == pickup_token,
        Order.tenant_id == tenant_id
    ).options(
        selectinload(Order.order_items).selectinload(OrderItem.product),
        selectinload(Order.customer)
    ).first()


def list_orders_for_counter(db: Session, counter_user: User, skip: int = 0, limit: int = 100,
                            lane_id: Optional[int] = None, unassigned: Optional[bool] = False) -> List[Order]:
    # ... (implementation from previous step) ...
    if not counter_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Counter staff not associated with a tenant.")

    query = db.query(Order).filter(
        Order.tenant_id == counter_user.tenant_id,
        Order.status == DBOrderStatusEnum.READY_FOR_PICKUP
    ).options(selectinload(Order.order_items), selectinload(Order.customer), selectinload(Order.pickup_slot))

    if lane_id is not None:
        query = query.filter(Order.assigned_lane_id == lane_id)
    if unassigned:
        query = query.filter(Order.assigned_lane_id == None) # type: ignore

    return query.order_by(Order.updated_at.desc()).offset(skip).limit(limit).all() # type: ignore

def prepare_order_verification_data(db: Session, order: Order) -> OrderVerificationDataResponse:
    # ... (implementation from previous step) ...
    if not order.identity_verification_product_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Order identity verification product not set.")

    verification_product = db.query(Product).filter(Product.id == order.identity_verification_product_id).first()

    other_hints = []
    # Ensure order.order_items is loaded; it should be if order is from get_order_by_pickup_token or get_order_details
    if order.order_items:
        for item in order.order_items[:3]:
            if item.product and item.product_id != order.identity_verification_product_id:
                other_hints.append(item.product.name) # type: ignore

    return OrderVerificationDataResponse(
        order_id=order.id, # type: ignore
        pickup_token=order.pickup_token, # type: ignore
        customer_username=order.customer.username if order.customer else "Guest", # type: ignore
        status=OrderStatusEnum(order.status.value), # type: ignore
        identity_verification_product_name=verification_product.name if verification_product else "Unknown Product", # type: ignore
        identity_verification_product_description=verification_product.description if verification_product else "", # type: ignore
        other_item_hints=other_hints
    )

def counter_complete_order_pickup(db: Session, order: Order, counter_user: User,
                                  request_data: CounterOrderCompleteRequest,
                                  lane_service_module: Any) -> Order:
    # ... (implementation from previous step) ...
    if order.tenant_id != counter_user.tenant_id: # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this tenant's order.")

    if order.status not in [DBOrderStatusEnum.READY_FOR_PICKUP, DBOrderStatusEnum.PROCESSING]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order cannot be completed from current status: {order.status.value}")

    order.status = DBOrderStatusEnum.COMPLETED # type: ignore

    assigned_lane_id = order.assigned_lane_id
    if assigned_lane_id:
        order.assigned_lane_id = None # type: ignore
        lane_service_module.clear_lane_and_set_open(db, lane_id=assigned_lane_id, tenant_id=order.tenant_id) # type: ignore

    db.add(order)
    db.commit()
    db.refresh(order)
    return order

# --- POS Service Function ---
def create_pos_order(
    db: Session,
    pos_order_in: POSOrderCreateRequest,
    staff_user: User
) -> Order:
    if not staff_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff performing POS sale must belong to a tenant.")

    # Basic idempotency placeholder
    if pos_order_in.idempotency_key:
        # Check cache/DB for existing order with this key; if found and matches, return it.
        # If found but doesn't match (e.g. different payload), raise conflict.
        pass

    order_items_to_create: List[OrderItem] = []
    current_total_amount = decimal.Decimal("0.00")

    for item_in in pos_order_in.items:
        product = product_service.get_product_by_id(db, product_id=item_in.product_id, tenant_id=staff_user.tenant_id)
        if not product:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product with ID {item_in.product_id} not found.")
        if product.stock_quantity < item_in.quantity: # type: ignore
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient stock for product {product.name} (ID: {item_in.product_id}). Available: {product.stock_quantity}, Requested: {item_in.quantity}")

        order_items_to_create.append(
            OrderItem(
                product_id=item_in.product_id,
                quantity=item_in.quantity,
                price_at_purchase=product.price # type: ignore
            )
        )
        current_total_amount += (product.price * item_in.quantity) # type: ignore

    db_order = Order(
        user_id=staff_user.id,
        tenant_id=staff_user.tenant_id,
        order_type=DBOrderTypeEnum.POS_SALE,
        status=DBOrderStatusEnum.COMPLETED,
        payment_status=DBPaymentStatusEnum.PAID,
        total_amount=current_total_amount,
        # payment_details={"method": pos_order_in.payment_method} # Add if Order model has this field
    )

    db_order.order_items.extend(order_items_to_create)
    db.add(db_order)
    # Must flush to get order_id for items if they are not yet associated via backref.
    # However, SQLAlchemy handles this with relationships usually.

    for item_data in pos_order_in.items:
        product_to_update = db.query(Product).filter(Product.id == item_data.product_id, Product.tenant_id == staff_user.tenant_id).first()
        if product_to_update:
            product_to_update.stock_quantity -= item_data.quantity # type: ignore
            product_to_update.version += 1 # type: ignore
            db.add(product_to_update)
        else:
            db.rollback() # Should not happen due to earlier check
            raise HTTPException(status_code=500, detail="Product stock update failed unexpectedly during POS transaction.")

    db.commit()
    db.refresh(db_order)
    # Eager load for response
    db.refresh(db_order, attribute_names=['order_items.product']) # type: ignore
    return db_order
