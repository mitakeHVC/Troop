import pytest
from sqlalchemy.orm import Session as SQLAlchemySession
from fastapi import HTTPException
import datetime
import decimal

from app.services import order_service, product_service, user_service, timeslot_service # All services
from app.schemas.order_schemas import CartItemCreateRequest, CheckoutRequestSchema # Schemas used by order_service
from app.schemas.user_schemas import UserCreate, UserRoleEnum
from app.schemas.product_schemas import ProductCreate
from app.schemas.timeslot_schemas import PickupTimeSlotCreate
from app.models.sql_models import (
    Tenant, User, Product, Order, OrderItem, PickupTimeSlot,
    DBOrderStatusEnum, # Corrected: Import DB enums from models.sql_models
    DBOrderTypeEnum,
    DBPaymentStatusEnum,
    DBUserRoleEnum
)
# For mocking or direct use if conftest setup is comprehensive
# from app.core.config import settings # For any config related logic if needed

# --- Fixtures ---
@pytest.fixture(scope="function") # Use function scope for better test isolation for order tests
def order_test_tenant(db_session: SQLAlchemySession) -> Tenant:
    tenant = Tenant(name=f"OrderTestTenant_{random.randint(1000,9999)}") # Unique name
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant

@pytest.fixture(scope="function")
def order_test_customer(db_session: SQLAlchemySession, order_test_tenant: Tenant) -> User:
    # Ensure unique username/email for each test run if tests are not fully isolated by DB rollback alone
    # or if other tests create users. For now, simple name.
    user_data = UserCreate(
        username=f"cartcust_{random.randint(1000,9999)}",
        email=f"cart_{random.randint(1000,9999)}@ex.com",
        password="pw",
        role=UserRoleEnum.customer, # Pydantic enum for UserCreate
        tenant_id=order_test_tenant.id
    )
    user = user_service.create_user(db_session, user=user_data)
    return user

@pytest.fixture(scope="function")
def order_test_product(db_session: SQLAlchemySession, order_test_tenant: Tenant) -> Product:
    prod_data = ProductCreate(
        name="CartProduct",
        sku=f"CARTP_{random.randint(1000,9999)}",
        price=decimal.Decimal("10.00"),
        stock_quantity=5 # Initial stock
    )
    product = product_service.create_product(db_session, product_in=prod_data, tenant_id=order_test_tenant.id)
    return product

@pytest.fixture(scope="function")
def order_test_product_nostock(db_session: SQLAlchemySession, order_test_tenant: Tenant) -> Product:
    prod_data = ProductCreate(
        name="NoStockProduct",
        sku=f"NOSTOCK_{random.randint(1000,9999)}",
        price=decimal.Decimal("5.00"),
        stock_quantity=0
    )
    product = product_service.create_product(db_session, product_in=prod_data, tenant_id=order_test_tenant.id)
    return product

@pytest.fixture(scope="function")
def order_test_slot(db_session: SQLAlchemySession, order_test_tenant: Tenant) -> PickupTimeSlot:
    slot_data = PickupTimeSlotCreate(
        date=datetime.date.today() + datetime.timedelta(days=1), # Ensure future date
        start_time=datetime.time(10,0),
        end_time=datetime.time(11,0),
        capacity=3 # Initial capacity
    )
    slot = timeslot_service.create_timeslot(db_session, timeslot_in=slot_data, tenant_id=order_test_tenant.id)
    return slot

# --- Test Functions ---
def test_get_or_create_cart(db_session: SQLAlchemySession, order_test_customer: User):
    cart = order_service.get_cart_by_user_id(db_session, user_id=order_test_customer.id, tenant_id=order_test_customer.tenant_id, create_if_not_exists=True) # type: ignore
    assert cart is not None
    assert cart.status == DBOrderStatusEnum.CART # Check DB enum
    assert cart.user_id == order_test_customer.id
    assert cart.tenant_id == order_test_customer.tenant_id
    assert cart.total_amount == decimal.Decimal("0.00")

    # Call again, should return the same cart
    cart_again = order_service.get_cart_by_user_id(db_session, user_id=order_test_customer.id, tenant_id=order_test_customer.tenant_id, create_if_not_exists=True) # type: ignore
    assert cart_again is not None
    assert cart_again.id == cart.id

def test_add_item_to_cart(db_session: SQLAlchemySession, order_test_customer: User, order_test_product: Product):
    cart = order_service.get_cart_by_user_id(db_session, user_id=order_test_customer.id, tenant_id=order_test_customer.tenant_id, create_if_not_exists=True) # type: ignore

    cart = order_service.add_item_to_cart(db_session, cart_order=cart, product_id=order_test_product.id, quantity=2) # type: ignore
    assert len(cart.order_items) == 1
    assert cart.order_items[0].quantity == 2
    assert cart.order_items[0].price_at_purchase == order_test_product.price
    assert cart.total_amount == order_test_product.price * 2 # type: ignore

    # Add more of the same product
    cart = order_service.add_item_to_cart(db_session, cart_order=cart, product_id=order_test_product.id, quantity=1) # type: ignore
    assert len(cart.order_items) == 1
    assert cart.order_items[0].quantity == 3
    assert cart.total_amount == order_test_product.price * 3 # type: ignore

def test_add_item_to_cart_insufficient_stock_service(db_session: SQLAlchemySession, order_test_customer: User, order_test_product: Product): # Renamed
    cart = order_service.get_cart_by_user_id(db_session, user_id=order_test_customer.id, tenant_id=order_test_customer.tenant_id, create_if_not_exists=True) # type: ignore

    with pytest.raises(HTTPException) as excinfo:
        # order_test_product has stock_quantity = 5
        order_service.add_item_to_cart(db_session, cart_order=cart, product_id=order_test_product.id, quantity=6) # type: ignore
    assert excinfo.value.status_code == 400
    assert "Not enough stock" in excinfo.value.detail # Check service layer message

def test_checkout_cart_success(
    db_session: SQLAlchemySession,
    order_test_customer: User,
    order_test_product: Product,
    order_test_slot: PickupTimeSlot
):
    cart = order_service.get_cart_by_user_id(db_session, user_id=order_test_customer.id, tenant_id=order_test_customer.tenant_id, create_if_not_exists=True) # type: ignore
    order_service.add_item_to_cart(db_session, cart_order=cart, product_id=order_test_product.id, quantity=2) # type: ignore

    initial_stock = order_test_product.stock_quantity
    initial_slot_orders = order_test_slot.current_orders

    checkout_details = CheckoutRequestSchema(pickup_slot_id=order_test_slot.id)
    confirmed_order = order_service.checkout_cart(db_session, cart_order=cart, checkout_details=checkout_details)

    assert confirmed_order.status == DBOrderStatusEnum.ORDER_CONFIRMED
    assert confirmed_order.payment_status == DBPaymentStatusEnum.PAID
    assert confirmed_order.pickup_slot_id == order_test_slot.id
    assert confirmed_order.pickup_token is not None
    assert confirmed_order.identity_verification_product_id == order_test_product.id # Since it's the only item

    db_session.refresh(order_test_product) # Refresh to get updated stock
    db_session.refresh(order_test_slot)    # Refresh to get updated current_orders

    assert order_test_product.stock_quantity == initial_stock - 2 # type: ignore
    assert order_test_slot.current_orders == initial_slot_orders + 1 # type: ignore

def test_checkout_cart_insufficient_stock_at_checkout_service( # Renamed
    db_session: SQLAlchemySession,
    order_test_customer: User,
    order_test_product: Product,
    order_test_slot: PickupTimeSlot
):
    cart = order_service.get_cart_by_user_id(db_session, user_id=order_test_customer.id, tenant_id=order_test_customer.tenant_id, create_if_not_exists=True) # type: ignore
    order_service.add_item_to_cart(db_session, cart_order=cart, product_id=order_test_product.id, quantity=3) # type: ignore

    # Simulate stock changing after adding to cart
    # Fetch product within session to update
    product_in_session = db_session.query(Product).filter(Product.id == order_test_product.id).first()
    assert product_in_session is not None
    product_in_session.stock_quantity = 1 # type: ignore
    db_session.commit()
    db_session.refresh(product_in_session)

    checkout_details = CheckoutRequestSchema(pickup_slot_id=order_test_slot.id)
    with pytest.raises(HTTPException) as excinfo:
        order_service.checkout_cart(db_session, cart_order=cart, checkout_details=checkout_details)
    assert excinfo.value.status_code == 400
    assert "out of stock or insufficient quantity" in excinfo.value.detail # Service specific message

def test_checkout_cart_slot_full_service( # Renamed
    db_session: SQLAlchemySession,
    order_test_customer: User,
    order_test_product: Product,
    order_test_slot: PickupTimeSlot
):
    # Fill the slot to capacity
    order_test_slot.current_orders = order_test_slot.capacity # type: ignore
    db_session.add(order_test_slot)
    db_session.commit()
    db_session.refresh(order_test_slot)

    cart = order_service.get_cart_by_user_id(db_session, user_id=order_test_customer.id, tenant_id=order_test_customer.tenant_id, create_if_not_exists=True) # type: ignore
    order_service.add_item_to_cart(db_session, cart_order=cart, product_id=order_test_product.id, quantity=1) # type: ignore

    checkout_details = CheckoutRequestSchema(pickup_slot_id=order_test_slot.id)
    with pytest.raises(HTTPException) as excinfo:
        order_service.checkout_cart(db_session, cart_order=cart, checkout_details=checkout_details)
    assert excinfo.value.status_code == 400
    assert "Selected pickup slot is not available or full" in excinfo.value.detail # Service specific message
