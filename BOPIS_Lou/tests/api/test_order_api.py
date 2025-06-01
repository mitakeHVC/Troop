import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as SQLAlchemySession
from typing import Optional, Dict, Any # For type hinting

from app.models.sql_models import Tenant, User, Product, PickupTimeSlot, Order, OrderItem # Base models
from app.models.sql_models import UserRole as DBUserRoleEnum # DB Enums
from app.models.sql_models import OrderStatus as DBOrderStatusEnum
from app.core.security import create_access_token, get_password_hash
from app.schemas.product_schemas import ProductCreate
from app.schemas.timeslot_schemas import PickupTimeSlotCreate
import datetime
import decimal
import random # For unique names/SKUs

# Helper to create user (can be in conftest.py or shared test utils)
def create_test_user_for_orders(db_session: SQLAlchemySession, username: str, role: DBUserRoleEnum, tenant_id: Optional[int] = None, email_suffix: str = "@example.com") -> User:
    user = User(
        username=username,
        email=f"{username}{email_suffix}",
        password_hash=get_password_hash("testpassword"),
        role=role,
        tenant_id=tenant_id,
        is_active=True
    )
    db_session.add(user); db_session.commit(); db_session.refresh(user)
    return user

# Helper to get auth headers (can be in conftest.py or shared test utils)
def get_auth_headers_for_orders(user_id: int, role: str, tenant_id: Optional[int]) -> Dict[str, str]:
    token = create_access_token(subject=str(user_id), role=role, tenant_id=tenant_id)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function") # Function scope for better isolation
def order_setup(db_session: SQLAlchemySession) -> Dict[str, Any]:
    rand_id = random.randint(1000, 9999)
    tenant = Tenant(name=f"OrderAPITestTenant_{rand_id}"); db_session.add(tenant); db_session.commit(); db_session.refresh(tenant)

    customer = create_test_user_for_orders(db_session, f"ordercust_{rand_id}", DBUserRoleEnum.customer, tenant.id)

    product1 = Product(name="OrderProd1", sku=f"ORDERP01_{rand_id}", price=decimal.Decimal("10.00"), stock_quantity=5, tenant_id=tenant.id, version=1)
    product2 = Product(name="OrderProd2_NoStock", sku=f"ORDERP02_{rand_id}", price=decimal.Decimal("5.00"), stock_quantity=0, tenant_id=tenant.id, version=1)
    db_session.add_all([product1, product2]); db_session.commit();
    db_session.refresh(product1); db_session.refresh(product2)

    # Ensure slot_date is in the future to be valid
    slot_date = datetime.date.today() + datetime.timedelta(days=1)
    slot = PickupTimeSlot(date=slot_date, start_time=datetime.time(10,0), end_time=datetime.time(11,0), capacity=3, tenant_id=tenant.id, current_orders=0, is_active=True)
    db_session.add(slot); db_session.commit(); db_session.refresh(slot)

    headers = get_auth_headers_for_orders(customer.id, customer.role.value, customer.tenant_id) # Use .value for enum
    return {"customer": customer, "product1": product1, "product2": product2, "slot": slot, "headers": headers, "tenant": tenant}

def test_cart_operations_and_checkout_success(client: TestClient, db_session: SQLAlchemySession, order_setup: Dict[str, Any]):
    headers = order_setup["headers"]
    product1 = order_setup["product1"] # Get product from setup
    slot = order_setup["slot"] # Get slot from setup

    # Get cart (should be created if none)
    response_get_cart = client.get("/orders/cart", headers=headers)
    assert response_get_cart.status_code == 200, response_get_cart.text
    cart = response_get_cart.json()
    cart_order_id = cart["id"]
    assert cart["status"] == DBOrderStatusEnum.CART.value

    # Add item to cart
    item_data = {"product_id": product1.id, "quantity": 2}
    response_add_item = client.post(f"/orders/cart/items", json=item_data, headers=headers)
    assert response_add_item.status_code == 200, response_add_item.text
    cart = response_add_item.json()
    assert len(cart["order_items"]) == 1
    assert cart["order_items"][0]["quantity"] == 2
    assert cart["total_amount"] == "20.00"

    # Checkout
    checkout_data = {"pickup_slot_id": slot.id}
    response_checkout = client.post(f"/orders/{cart_order_id}/checkout", json=checkout_data, headers=headers)
    assert response_checkout.status_code == 200, response_checkout.text
    confirmed_order = response_checkout.json()
    assert confirmed_order["status"] == DBOrderStatusEnum.ORDER_CONFIRMED.value
    assert confirmed_order["pickup_slot_id"] == slot.id
    assert confirmed_order["pickup_token"] is not None
    assert confirmed_order["identity_verification_product_id"] == product1.id # Only one item type

    db_session.refresh(product1) # Refresh product from DB
    db_session.refresh(slot)    # Refresh slot from DB
    assert product1.stock_quantity == 3 # 5 - 2
    assert slot.current_orders == 1

def test_checkout_product_out_of_stock_api(client: TestClient, db_session: SQLAlchemySession, order_setup: Dict[str, Any]): # Renamed
    headers = order_setup["headers"]
    product_no_stock = order_setup["product2"] # product2 has 0 stock
    slot = order_setup["slot"]

    response_get_cart = client.get("/orders/cart", headers=headers)
    assert response_get_cart.status_code == 200
    cart_order_id = response_get_cart.json()["id"]

    item_data = {"product_id": product_no_stock.id, "quantity": 1}
    # Attempt to add out-of-stock item to cart
    # The service add_item_to_cart checks stock and should raise 400
    response_add_item = client.post(f"/orders/cart/items", json=item_data, headers=headers)
    assert response_add_item.status_code == 400
    assert "Not enough stock" in response_add_item.json()["detail"]

    # If somehow item was added (e.g. race condition or different add_item logic) test checkout failure:
    # This part of the test might be redundant if add_item_to_cart already prevents it.
    # For robustness, if we assume an item could be in cart due to earlier stock availability:
    # Manually create an item in cart with a product that then goes out of stock
    # For now, the above test for add_item_to_cart covers this scenario at add time.

def test_checkout_invalid_slot_api(client: TestClient, db_session: SQLAlchemySession, order_setup: Dict[str, Any]): # Renamed
    headers = order_setup["headers"]
    product1 = order_setup["product1"]

    response_get_cart = client.get("/orders/cart", headers=headers)
    assert response_get_cart.status_code == 200
    cart_order_id = response_get_cart.json()["id"]

    item_data = {"product_id": product1.id, "quantity": 1}
    response_add_item = client.post(f"/orders/cart/items", json=item_data, headers=headers)
    assert response_add_item.status_code == 200

    checkout_data = {"pickup_slot_id": 99999} # Non-existent slot ID
    response_checkout = client.post(f"/orders/{cart_order_id}/checkout", json=checkout_data, headers=headers)
    assert response_checkout.status_code == 400
    assert "Selected pickup slot is not available or full" in response_checkout.json()["detail"] # Message from service

def test_view_orders_rbac(client: TestClient, db_session: SQLAlchemySession, order_setup: Dict[str, Any]):
    customer_headers = order_setup["headers"]
    customer_id = order_setup["customer"].id
    tenant_id = order_setup["tenant"].id

    # Create an order for the customer (from previous test logic for success)
    response = client.get("/orders/cart", headers=customer_headers)
    cart_order_id = response.json()["id"]
    item_data = {"product_id": order_setup["product1"].id, "quantity": 1}
    client.post(f"/orders/cart/items", json=item_data, headers=customer_headers)
    checkout_data = {"pickup_slot_id": order_setup["slot"].id}
    response = client.post(f"/orders/{cart_order_id}/checkout", json=checkout_data, headers=customer_headers)
    assert response.status_code == 200
    confirmed_order_id = response.json()["id"]

    # Customer views their own orders
    response = client.get("/orders/", headers=customer_headers)
    assert response.status_code == 200
    orders = response.json()
    assert len(orders) >= 1
    assert any(o["id"] == confirmed_order_id for o in orders)

    # Create tenant admin
    t_admin = create_test_user_for_orders(db_session, f"ordertenadmin_{random.randint(1000,9999)}", DBUserRoleEnum.tenant_admin, tenant_id)
    t_admin_headers = get_auth_headers_for_orders(t_admin.id, t_admin.role.value, t_admin.tenant_id)

    # Tenant admin views orders for their tenant
    response = client.get("/orders/", headers=t_admin_headers)
    assert response.status_code == 200
    orders_admin = response.json()
    assert any(o["id"] == confirmed_order_id for o in orders_admin) # Customer's order should be visible

    # Create user in another tenant
    other_tenant = Tenant(name=f"OtherOrderTenant_{random.randint(1000,9999)}"); db_session.add(other_tenant); db_session.commit(); db_session.refresh(other_tenant)
    other_customer = create_test_user_for_orders(db_session, f"othercust_{random.randint(1000,9999)}", DBUserRoleEnum.customer, other_tenant.id)
    other_customer_headers = get_auth_headers_for_orders(other_customer.id, other_customer.role.value, other_customer.tenant_id)

    # Other customer tries to view original customer's order by ID
    response = client.get(f"/orders/{confirmed_order_id}", headers=other_customer_headers)
    assert response.status_code == 403 # Forbidden (or 404 if service hides existence)
    assert "Not authorized to access this order" in response.json()["detail"]
