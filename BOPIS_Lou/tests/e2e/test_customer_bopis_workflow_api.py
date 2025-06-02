import pytest
import pytest_asyncio # Added
import httpx
from typing import Dict, Callable, Awaitable, Any
import datetime

from app.models.sql_models import User as UserModel, Tenant as TenantModel
from app.schemas.user_schemas import UserRoleEnum, UserResponse
from app.schemas.tenant_schemas import TenantResponse as TenantApiResponse # Alias to avoid clash if Tenant model imported
from app.schemas.product_schemas import ProductCreate, ProductResponse
from app.schemas.timeslot_schemas import PickupTimeSlotCreate, PickupTimeSlotResponse
# Use the actual schema names from order_schemas.py for creating instances if needed by tests for POST bodies
# For response validation, the structure is more important than the exact class name.
from app.schemas.order_schemas import CartItemCreateRequest as CartItemCreate, OrderResponse, CheckoutRequestSchema as CheckoutRequest, OrderStatusEnum

pytestmark = pytest.mark.asyncio

# Re-use or adapt tenant_and_admin_setup fixture for setting up tenant context
# For simplicity, we can copy and specialize it or make it more generic in conftest.
# Let's assume a fixture `prepared_tenant_for_customer_test` exists or we build it here.

@pytest_asyncio.fixture # Changed
async def prepared_tenant_for_customer_test(
    async_client: httpx.AsyncClient,
    create_test_user_directly: Callable[..., Awaitable[UserModel]],
    get_auth_headers: Callable[..., Awaitable[Dict[str, str]]]
):
    # 1. Super Admin creates a Tenant
    super_admin_username = "sa_customer_test"
    super_admin_email = "sa_customer_test@example.com"
    super_admin_password = "sapassword"
    await create_test_user_directly(
        username=super_admin_username, email=super_admin_email, password=super_admin_password, role=UserRoleEnum.super_admin
    )
    sa_headers = await get_auth_headers(username=super_admin_username, password=super_admin_password)

    tenant_name = "BOPIS Mart"
    response = await async_client.post("/tenants/", json={"name": tenant_name}, headers=sa_headers) # Added trailing slash
    response.raise_for_status()
    tenant_api_resp = TenantApiResponse(**response.json())

    # 2. Create Tenant Admin for this Tenant
    tenant_admin_username = "ta_customer_test"
    tenant_admin_email = "ta_customer_test@example.com"
    tenant_admin_password = "tapassword"
    await create_test_user_directly(
        username=tenant_admin_username, email=tenant_admin_email, password=tenant_admin_password,
        role=UserRoleEnum.tenant_admin, tenant_id=tenant_api_resp.id
    )
    ta_headers = await get_auth_headers(username=tenant_admin_username, password=tenant_admin_password)

    # 3. Tenant Admin creates a Product
    product_data = ProductCreate(
        name="Test E2E Product", price=12.99, sku=f"E2E_SKU_{tenant_api_resp.id}_001", stock_quantity=50
    )
    response = await async_client.post("/products/", json=product_data.model_dump(mode='json'), headers=ta_headers) # Changed to model_dump(mode='json')
    response.raise_for_status()
    created_product = ProductResponse(**response.json())

    # 4. Tenant Admin creates a Pickup Time Slot
    slot_date = datetime.date.today() + datetime.timedelta(days=1)
    timeslot_data = PickupTimeSlotCreate(
        date=slot_date,
        start_time=datetime.time(14, 0),
        end_time=datetime.time(15, 0),
        capacity=10
    )
    # Use .model_dump() for Pydantic v2 if .dict() is deprecated and causing issues
    response = await async_client.post("/timeslots/", json=timeslot_data.model_dump(mode='json', exclude_unset=True), headers=ta_headers) # Changed to model_dump(mode='json')
    response.raise_for_status()
    created_timeslot = PickupTimeSlotResponse(**response.json())

    return tenant_api_resp, created_product, created_timeslot, ta_headers

async def test_customer_bopis_full_workflow(
    async_client: httpx.AsyncClient,
    prepared_tenant_for_customer_test: Any, # Fixture
    create_customer_user_via_api: Callable[..., Awaitable[Dict[str, Any]]], # from e2e/conftest.py
    get_auth_headers: Callable[..., Awaitable[Dict[str, str]]]     # from e2e/conftest.py
):
    tenant_api_resp, product, timeslot, _ = prepared_tenant_for_customer_test

    # 1. Customer Registration
    customer_username = "bopis_customer"
    customer_email = "bopis_customer@example.com"
    customer_password = "customerpassword"

    await create_customer_user_via_api(
        username=customer_username, email=customer_email, password=customer_password, tenant_id=tenant_api_resp.id
    )

    # 2. Customer Login
    customer_headers = await get_auth_headers(username=customer_username, password=customer_password)

    # 3. Customer views products for the tenant
    # Assuming product listing for customer needs tenant_id as query param
    # No change needed here, /? is standard for query params, FastAPI handles /products/ or /products for this
    response = await async_client.get(f"/products/?tenantId={tenant_api_resp.id}", headers=customer_headers) # Changed tenant_id to tenantId
    response.raise_for_status()
    products_list = response.json() # Expect a list
    assert isinstance(products_list, list)
    assert len(products_list) > 0
    assert any(p["id"] == product.id for p in products_list)

    # 4. Customer adds product to cart
    response = await async_client.get("/orders/cart", headers=customer_headers) # Removed trailing slash
    response.raise_for_status()
    cart = OrderResponse(**response.json()) # Initial cart or existing one

    # Use CartItemCreate (aliased from CartItemCreateRequest) for the request body
    cart_item_data = CartItemCreate(product_id=product.id, quantity=1)
    response = await async_client.post(f"/orders/cart/items", json=cart_item_data.model_dump(), headers=customer_headers) # Removed trailing slash
    response.raise_for_status()
    updated_cart = OrderResponse(**response.json())
    assert len(updated_cart.order_items) == 1
    assert updated_cart.order_items[0].product_id == product.id
    cart_order_id = updated_cart.id

    # 5. Customer lists available timeslots
    response = await async_client.get(f"/timeslots/tenant/{tenant_api_resp.id}/available", headers=customer_headers) # Removed trailing slash
    response.raise_for_status()
    available_slots_list = response.json() # Expect a list
    assert isinstance(available_slots_list, list)
    assert len(available_slots_list) > 0
    assert any(ts["id"] == timeslot.id for ts in available_slots_list)

    # 6. Customer checks out
    # Use CheckoutRequest (aliased from CheckoutRequestSchema) for the request body
    checkout_data = CheckoutRequest(pickup_slot_id=timeslot.id)
    response = await async_client.post(f"/orders/{cart_order_id}/checkout", json=checkout_data.model_dump(), headers=customer_headers) # Removed trailing slash
    response.raise_for_status()
    confirmed_order = OrderResponse(**response.json())

    assert confirmed_order.status == OrderStatusEnum.ORDER_CONFIRMED # Using the imported enum
    assert confirmed_order.pickup_slot_id == timeslot.id
    assert confirmed_order.pickup_token is not None
    # Price check: product.price is Decimal, ensure comparison is appropriate
    assert confirmed_order.total_amount == product.price * 1

    # 7. Customer views their order
    response = await async_client.get(f"/orders/{confirmed_order.id}", headers=customer_headers) # Removed trailing slash
    response.raise_for_status()
    final_order_view = OrderResponse(**response.json())

    assert final_order_view.id == confirmed_order.id
    assert final_order_view.order_items[0].product_id == product.id
    assert final_order_view.pickup_slot_id == timeslot.id
