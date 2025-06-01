"""
Service layer for order management, including cart, checkout, POS, and workflows.

This module handles the business logic for:
- Shopping cart operations (add, update, remove items, view cart).
- BOPIS order checkout process (stock validation, slot booking, payment (mocked)).
- POS order creation and stock management.
- Order viewing and status updates for different user roles (customer, picker, counter).
- Basic notification generation for order status changes.
"""
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func as sql_func, or_
from typing import List, Optional, Any
import uuid
import random
import decimal
from fastapi import HTTPException, status

from app.models.sql_models import (
    Order, OrderItem, Product, PickupTimeSlot, User, Notification, Lane, StaffAssignment,
    OrderStatus as DBOrderStatusEnum,
    OrderType as DBOrderTypeEnum,
    PaymentStatus as DBPaymentStatusEnum,
    UserRole as DBUserRoleEnum
)
from app.schemas.order_schemas import (
    OrderItemCreate, OrderItemUpdate, CheckoutRequestSchema, OrderCreate, OrderStatusEnum, OrderTypeEnum
)
from app.schemas.picker_schemas import PickerReadyForPickupRequest
from app.schemas.counter_schemas import OrderVerificationDataResponse, CounterOrderCompleteRequest
from app.schemas.pos_schemas import POSOrderCreateRequest

from app.services import product_service, timeslot_service
# from app.services import lane_service # Imported dynamically in counter_complete_order_pickup

def _recalculate_cart_total(db: Session, cart_order: Order) -> None:
    """
    Recalculates the total amount for a given order based on its items.
    This function does not commit the session.

    Args:
        db: SQLAlchemy database session.
        cart_order: The Order object (typically a cart) to recalculate.
    """
    if not cart_order:
        return
    current_total = decimal.Decimal("0.00")
    for item in cart_order.order_items:
        if item.price_at_purchase is not None and item.quantity is not None:
            current_total += item.price_at_purchase * item.quantity
    cart_order.total_amount = current_total
    db.add(cart_order)


def get_cart_by_user_id(db: Session, user_id: int, tenant_id: int, create_if_not_exists: bool = False) -> Optional[Order]:
    """
    Retrieves the active cart (Order with status CART) for a given user and tenant.
    If `create_if_not_exists` is True, a new cart is created if one doesn't exist.

    Args:
        db: SQLAlchemy database session.
        user_id: ID of the user.
        tenant_id: ID of the tenant context for the cart.
        create_if_not_exists: Flag to create a cart if none is found.

    Returns:
        The active cart Order object if found or created, else None.
    """
    cart = db.query(Order).options(
        selectinload(Order.order_items).selectinload(OrderItem.product)
    ).filter(
        Order.user_id == user_id,
        Order.tenant_id == tenant_id,
        Order.status == DBOrderStatusEnum.CART
    ).first()

    if not cart and create_if_not_exists:
        # Use Pydantic OrderTypeEnum for OrderCreate schema
        order_data = OrderCreate(user_id=user_id, tenant_id=tenant_id, order_type=OrderTypeEnum.BOPIS)
        cart = Order(
            user_id=order_data.user_id,
            tenant_id=order_data.tenant_id,
            order_type=DBOrderTypeEnum[order_data.order_type.value], # Convert Pydantic enum to DB enum
            status=DBOrderStatusEnum.CART,
            payment_status=DBPaymentStatusEnum.UNPAID,
            total_amount=decimal.Decimal("0.00")
        )
        db.add(cart)
        db.commit() # Commit cart creation immediately
        db.refresh(cart)
    return cart

def add_item_to_cart(db: Session, cart_order: Order, product_id: int, quantity: int) -> Order:
    """
    Adds a product item to the specified cart or updates its quantity if it already exists.
    Validates product existence and stock before adding. Recalculates cart total.

    Args:
        db: SQLAlchemy database session.
        cart_order: The cart (Order object) to add items to.
        product_id: ID of the product to add.
        quantity: Quantity of the product to add.

    Raises:
        HTTPException: If order is not a cart, product not found, or insufficient stock.

    Returns:
        The updated cart Order object with items and product details eager-loaded.
    """
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
            price_at_purchase=product.price # type: ignore
        )
        db.add(new_item)
        if new_item not in cart_order.order_items: # Ensure collection is updated if not using backref immediately
            cart_order.order_items.append(new_item)

    _recalculate_cart_total(db, cart_order)
    db.commit()
    db.refresh(cart_order)
    # Re-fetch with eager loading for consistent response structure
    refreshed_cart = db.query(Order).options(selectinload(Order.order_items).selectinload(OrderItem.product)).filter(Order.id == cart_order.id).first()
    return refreshed_cart # type: ignore

def update_cart_item_quantity(db: Session, cart_order: Order, order_item_id: int, new_quantity: int) -> Order:
    """
    Updates the quantity of an existing item in the cart.
    Recalculates cart total. Stock check is deferred to checkout.

    Args:
        db: SQLAlchemy database session.
        cart_order: The cart (Order object).
        order_item_id: ID of the OrderItem to update.
        new_quantity: The new quantity for the item.

    Raises:
        HTTPException: If order is not a cart or item not found.

    Returns:
        The updated cart Order object.
    """
    if cart_order.status != DBOrderStatusEnum.CART:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not a cart.")

    item_to_update = db.query(OrderItem).filter(
        OrderItem.id == order_item_id,
        OrderItem.order_id == cart_order.id
    ).first()

    if not item_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found.")

    # Stock check for the specific item being updated is not strictly enforced here;
    # final check occurs at checkout. This allows users to adjust quantities freely in cart.
    # product = product_service.get_product_by_id(db, product_id=item_to_update.product_id, tenant_id=cart_order.tenant_id)
    # if product and product.stock_quantity < new_quantity:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Not enough stock for {product.name}. Available: {product.stock_quantity}")

    item_to_update.quantity = new_quantity # type: ignore
    db.add(item_to_update)
    _recalculate_cart_total(db, cart_order)
    db.commit()
    db.refresh(cart_order)
    refreshed_cart = db.query(Order).options(selectinload(Order.order_items).selectinload(OrderItem.product)).filter(Order.id == cart_order.id).first()
    return refreshed_cart # type: ignore

def remove_cart_item(db: Session, cart_order: Order, order_item_id: int) -> Order:
    """
    Removes an item from the cart. Recalculates cart total.

    Args:
        db: SQLAlchemy database session.
        cart_order: The cart (Order object).
        order_item_id: ID of the OrderItem to remove.

    Raises:
        HTTPException: If order is not a cart or item not found.

    Returns:
        The updated cart Order object.
    """
    if cart_order.status != DBOrderStatusEnum.CART:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not a cart.")

    item_to_remove = next((item for item in cart_order.order_items if item.id == order_item_id), None)

    if not item_to_remove:
        item_to_remove_db = db.query(OrderItem).filter(OrderItem.id == order_item_id, OrderItem.order_id == cart_order.id).first()
        if not item_to_remove_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found.")
        item_to_remove = item_to_remove_db

    if item_to_remove in cart_order.order_items: # Ensure it's removed from collection for recalculation
        cart_order.order_items.remove(item_to_remove)

    db.delete(item_to_remove)
    _recalculate_cart_total(db, cart_order)
    db.commit()
    refreshed_cart = db.query(Order).options(selectinload(Order.order_items).selectinload(OrderItem.product)).filter(Order.id == cart_order.id).first()
    return refreshed_cart # type: ignore

def checkout_cart(db: Session, cart_order: Order, checkout_details: CheckoutRequestSchema) -> Order:
    """
    Processes the checkout for a given cart.
    This involves:
    - Validating items are in stock (using optimistic locking via product versions).
    - Validating the selected pickup slot.
    - Decrementing stock for all items.
    - Updating the pickup slot's current order count.
    - Changing order status to ORDER_CONFIRMED.
    - Generating a pickup token.
    All database operations are performed in a single transaction.

    Args:
        db: SQLAlchemy database session.
        cart_order: The cart (Order object with status CART).
        checkout_details: Pydantic schema with checkout information (pickup_slot_id).

    Raises:
        HTTPException: If cart is invalid, items out of stock, slot unavailable, or version conflicts.

    Returns:
        The confirmed Order object with updated details.
    """
    if cart_order.status != DBOrderStatusEnum.CART:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only an active cart can be checked out.")
    if not cart_order.order_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot checkout an empty cart.")

    # Fetch products with their current versions and check initial stock
    products_to_update_details = []
    for item in cart_order.order_items:
        product = product_service.get_product_by_id(db, product_id=item.product_id, tenant_id=cart_order.tenant_id) # type: ignore
        if not product or product.stock_quantity < item.quantity: # type: ignore
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product '{product.name if product else item.product_id}' is out of stock or has insufficient quantity for checkout.") # type: ignore
        products_to_update_details.append({
            "product_id": product.id, # type: ignore
            "name": product.name, # type: ignore
            "quantity_ordered": item.quantity,
            "expected_version": product.version # type: ignore
        })

    slot = timeslot_service.get_timeslot_by_id(db, timeslot_id=checkout_details.pickup_slot_id, tenant_id=cart_order.tenant_id) # type: ignore
    if not slot or not slot.is_active or slot.current_orders >= slot.capacity: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected pickup slot is not available or full.")

    # All pre-checks passed, attempt to decrement stock for all items
    for prod_detail in products_to_update_details:
        try:
            product_service.decrement_stock(
                db,
                product_id=prod_detail["product_id"],
                quantity=prod_detail["quantity_ordered"],
                tenant_id=cart_order.tenant_id, # type: ignore
                expected_version=prod_detail["expected_version"]
            )
        except HTTPException as e: # Catch issues from decrement_stock (e.g., 409 Conflict, 400 Insufficient)
            # Add more context to the error if needed
            raise HTTPException(status_code=e.status_code, detail=f"Checkout failed for product '{prod_detail['name']}': {e.detail}")

    # Update order status and details
    cart_order.status = DBOrderStatusEnum.ORDER_CONFIRMED # type: ignore
    cart_order.payment_status = DBPaymentStatusEnum.PAID # type: ignore
    cart_order.pickup_slot_id = checkout_details.pickup_slot_id # type: ignore
    cart_order.pickup_token = str(uuid.uuid4()) # type: ignore

    if cart_order.order_items:
        cart_order.identity_verification_product_id = random.choice(cart_order.order_items).product_id # type: ignore

    # Increment slot order count
    timeslot_service.increment_slot_order_count(db, timeslot_id=checkout_details.pickup_slot_id, tenant_id=cart_order.tenant_id) # type: ignore

    _recalculate_cart_total(db, cart_order) # Final total calculation
    db.add(cart_order)

    db.commit() # Single commit for the entire checkout operation
    db.refresh(cart_order)

    # Eager load details for the response
    refreshed_order = db.query(Order).options(
        selectinload(Order.order_items).selectinload(OrderItem.product),
        selectinload(Order.customer),
        selectinload(Order.pickup_slot)
    ).filter(Order.id == cart_order.id).first()
    return refreshed_order # type: ignore

def get_order_details(db: Session, order_id: int, user_id_for_auth: int, user_role_for_auth: DBUserRoleEnum, tenant_id_for_auth: Optional[int]) -> Optional[Order]:
    """
    Retrieves detailed information for a specific order, including related entities.
    Enforces access permissions based on the user's role and ownership.
    """
    # Fetch minimal data for permission check first
    order_owner_info = db.query(Order.user_id, Order.tenant_id, Order.status).filter(Order.id == order_id).first() # type: ignore
    if not order_owner_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    # Permission check logic
    if user_role_for_auth == DBUserRoleEnum.super_admin:
        pass # Super admin can access any order
    elif user_role_for_auth in [DBUserRoleEnum.tenant_admin, DBUserRoleEnum.picker, DBUserRoleEnum.counter]:
        if tenant_id_for_auth is None or order_owner_info.tenant_id != tenant_id_for_auth:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this order's tenant resources.")
    else: # Customer role
        if order_owner_info.user_id != user_id_for_auth:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this order.")

    # If authorized, fetch the full order with eager loading
    query = db.query(Order).options(
        selectinload(Order.order_items).selectinload(OrderItem.product).joinedload(Product.tenant),
        selectinload(Order.customer),
        selectinload(Order.pickup_slot),
        selectinload(Order.assigned_lane).selectinload(Lane.staff_assignments).selectinload(StaffAssignment.user)
    ).filter(Order.id == order_id)
    return query.first()


def list_orders_for_user(db: Session, user: User, skip: int = 0, limit: int = 100) -> List[Order]:
    """
    Lists orders with basic details, applying visibility rules based on user role.
    - Customers see their own orders.
    - Staff (picker, counter, tenant_admin) see orders for their tenant.
    - Super_admin sees all orders.
    """
    query = db.query(Order).options(
        selectinload(Order.order_items).selectinload(OrderItem.product), # Eager load for potential item counts or brief summaries
        selectinload(Order.pickup_slot),
        selectinload(Order.customer) # For identifying customer if admin/staff view
    )
    if user.role == DBUserRoleEnum.super_admin:
        # No specific filter for super_admin, they see all. Consider pagination carefully.
        pass
    elif user.role in [DBUserRoleEnum.tenant_admin, DBUserRoleEnum.picker, DBUserRoleEnum.counter]:
        if not user.tenant_id: # Should be caught by dependency or earlier checks
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context required for staff/admin.")
        query = query.filter(Order.tenant_id == user.tenant_id)
    else: # Customer
        query = query.filter(Order.user_id == user.id)

    return query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all() # type: ignore

# --- Picker Service Functions ---
def list_orders_for_picker(db: Session, picker_user: User, skip: int = 0, limit: int = 100) -> List[Order]:
    """Lists orders relevant to a picker (ORDER_CONFIRMED or PROCESSING in their tenant)."""
    if not picker_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Picker is not associated with a tenant.")

    query = db.query(Order).filter(
        Order.tenant_id == picker_user.tenant_id,
        or_(Order.status == DBOrderStatusEnum.ORDER_CONFIRMED, Order.status == DBOrderStatusEnum.PROCESSING)
    ).options(selectinload(Order.order_items)) # Eager load items for item_count calculation in router

    return query.order_by(Order.created_at.asc()).offset(skip).limit(limit).all() # Pick oldest first

def picker_start_order_processing(db: Session, order: Order, picker_user: User) -> Order:
    """Marks an order as PROCESSING by a picker."""
    if order.tenant_id != picker_user.tenant_id: # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this tenant's order.")
    if order.status != DBOrderStatusEnum.ORDER_CONFIRMED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order cannot be started; current status: {order.status.value}") # type: ignore

    order.status = DBOrderStatusEnum.PROCESSING # type: ignore
    # order.assigned_picker_id = picker_user.id # Optional: if tracking picker assignment
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

def picker_mark_order_ready(db: Session, order: Order, picker_user: User, request_data: PickerReadyForPickupRequest) -> Order:
    """Marks an order as READY_FOR_PICKUP by a picker and creates notifications."""
    if order.tenant_id != picker_user.tenant_id: # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this tenant's order.")
    if order.status != DBOrderStatusEnum.PROCESSING: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order cannot be marked ready; current status: {order.status.value}") # type: ignore

    order.status = DBOrderStatusEnum.READY_FOR_PICKUP # type: ignore
    # if request_data.notes: order.picker_notes = request_data.notes # Add field if needed
    db.add(order)

    # TODO: Refactor notification creation to a dedicated notification_service for more complex scenarios and targeting.
    users_to_notify = db.query(User).filter(
        User.tenant_id == order.tenant_id, # type: ignore
        User.is_active == True,
        or_(User.role == DBUserRoleEnum.tenant_admin, User.role == DBUserRoleEnum.counter)
    ).all()

    for user_to_notify in users_to_notify:
        notification_message = f"Order #{order.id} (Token: {order.pickup_token}) is now READY FOR PICKUP."
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
    """Retrieves an order by its pickup token, scoped to a tenant. Eager loads items and customer."""
    return db.query(Order).filter(
        Order.pickup_token == pickup_token,
        Order.tenant_id == tenant_id
    ).options(
        selectinload(Order.order_items).selectinload(OrderItem.product),
        selectinload(Order.customer)
    ).first()

def list_orders_for_counter(db: Session, counter_user: User, skip: int = 0, limit: int = 100,
                            lane_id: Optional[int] = None, unassigned: Optional[bool] = False) -> List[Order]:
    """Lists orders for counter staff (READY_FOR_PICKUP), with optional filters."""
    if not counter_user.tenant_id: # Should be caught by dependency
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Counter staff not associated with a tenant.")

    query = db.query(Order).filter(
        Order.tenant_id == counter_user.tenant_id,
        Order.status == DBOrderStatusEnum.READY_FOR_PICKUP
    ).options(selectinload(Order.order_items), selectinload(Order.customer), selectinload(Order.pickup_slot))

    if lane_id is not None:
        query = query.filter(Order.assigned_lane_id == lane_id)
    if unassigned:
        query = query.filter(Order.assigned_lane_id.is_(None)) # Corrected filter for NULL

    return query.order_by(Order.updated_at.desc()).offset(skip).limit(limit).all() # type: ignore

def prepare_order_verification_data(db: Session, order: Order) -> OrderVerificationDataResponse:
    """Prepares data to assist counter staff in verifying customer identity."""
    verification_product_name = "N/A"
    verification_product_description = "N/A"

    if not order.identity_verification_product_id and order.order_items:
        # If not set at checkout, pick one now (does not persist this choice on the order)
        chosen_item = random.choice(order.order_items)
        if chosen_item.product:
            verification_product_name = chosen_item.product.name # type: ignore
            verification_product_description = chosen_item.product.description # type: ignore
    elif order.identity_verification_product_id:
        # If it was set, fetch that product's details
        verification_product = db.query(Product).filter(Product.id == order.identity_verification_product_id).first()
        if verification_product:
            verification_product_name = verification_product.name # type: ignore
            verification_product_description = verification_product.description # type: ignore

    other_hints = []
    if order.order_items:
        for item in order.order_items[:3]: # Limit hints
            if item.product and item.product_id != order.identity_verification_product_id:
                other_hints.append(item.product.name) # type: ignore

    return OrderVerificationDataResponse(
        order_id=order.id, # type: ignore
        pickup_token=order.pickup_token, # type: ignore
        customer_username=order.customer.username if order.customer else "Guest", # type: ignore
        status=OrderStatusEnum(order.status.value), # type: ignore
        identity_verification_product_name=verification_product_name,
        identity_verification_product_description=verification_product_description,
        other_item_hints=other_hints
    )

def counter_complete_order_pickup(db: Session, order: Order, counter_user: User,
                                  request_data: CounterOrderCompleteRequest,
                                  lane_service_module: Any) -> Order:
    """Completes an order pickup, updates status, and clears lane if assigned."""
    if order.tenant_id != counter_user.tenant_id: # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this tenant's order.")

    if order.status not in [DBOrderStatusEnum.READY_FOR_PICKUP, DBOrderStatusEnum.PROCESSING]: # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order cannot be completed from current status: {order.status.value}") # type: ignore

    order.status = DBOrderStatusEnum.COMPLETED # type: ignore
    # if request_data.notes: order.counter_notes = request_data.notes # Add field if needed

    assigned_lane_id = order.assigned_lane_id
    if assigned_lane_id:
        order.assigned_lane_id = None # type: ignore
        if lane_service_module:
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
    """
    Creates a Point of Sale order.
    - Validates product stock.
    - Decrements stock using product_service.decrement_stock for optimistic locking.
    - Sets order status to COMPLETED and payment to PAID immediately.
    - All operations are within a single database transaction.
    """
    if not staff_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff performing POS sale must belong to a tenant.")

    if pos_order_in.idempotency_key:
        # TODO: Implement robust server-side idempotency key check against a persistent store.
        # e.g., check if key exists, if yes, return original response or error if payload differs.
        pass

    order_items_to_create: List[OrderItem] = []
    current_total_amount = decimal.Decimal("0.00")

    # Pre-fetch product details including version
    product_details_for_pos = []
    for item_in in pos_order_in.items:
        product = product_service.get_product_by_id(db, product_id=item_in.product_id, tenant_id=staff_user.tenant_id)
        if not product:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product with ID {item_in.product_id} not found.")
        if product.stock_quantity < item_in.quantity: # type: ignore
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient stock for product {product.name} (ID: {item_in.product_id}). Available: {product.stock_quantity}, Requested: {item_in.quantity}")
        product_details_for_pos.append({
            "product_db": product,
            "quantity_ordered": item_in.quantity,
            "price_at_purchase": product.price, # type: ignore
            "expected_version": product.version # type: ignore
        })
        current_total_amount += (product.price * item_in.quantity) # type: ignore

    db_order = Order(
        user_id=staff_user.id,
        tenant_id=staff_user.tenant_id,
        order_type=DBOrderTypeEnum.POS_SALE,
        status=DBOrderStatusEnum.COMPLETED,
        payment_status=DBPaymentStatusEnum.PAID,
        total_amount=current_total_amount,
        # payment_details field could store pos_order_in.payment_method
    )
    db.add(db_order)
    db.flush() # Get order_id for items

    for detail in product_details_for_pos:
        order_items_to_create.append(
            OrderItem(
                order_id=db_order.id,
                product_id=detail["product_db"].id,
                quantity=detail["quantity_ordered"],
                price_at_purchase=detail["price_at_purchase"]
            )
        )
        product_service.decrement_stock(
            db,
            product_id=detail["product_db"].id,
            quantity=detail["quantity_ordered"],
            tenant_id=staff_user.tenant_id, # type: ignore
            expected_version=detail["expected_version"]
        )

    db.add_all(order_items_to_create)

    db.commit()
    db.refresh(db_order)

    refreshed_order = db.query(Order).options(
        selectinload(Order.order_items).selectinload(OrderItem.product)
    ).filter(Order.id == db_order.id).first()
    return refreshed_order # type: ignore
