import pytest
import pytest_asyncio # Added
import httpx
from typing import Dict, Callable, Awaitable, Any

from app.models.sql_models import User as UserModel, Tenant as TenantModel
from app.schemas.user_schemas import UserRoleEnum, StaffCreate, UserResponse as StaffResponse # StaffResponse is UserResponse
from app.schemas.product_schemas import ProductCreate, ProductResponse
from app.schemas.tenant_schemas import TenantCreate, TenantResponse

pytestmark = pytest.mark.asyncio

# Helper fixture to create a tenant and a tenant admin for that tenant
@pytest_asyncio.fixture # Changed
async def tenant_and_admin_setup(
    async_client: httpx.AsyncClient,
    create_test_user_directly: Callable[..., Awaitable[UserModel]],
    get_auth_headers: Callable[..., Awaitable[Dict[str, str]]]
):
    # 1. Create Super Admin
    super_admin_username = "test_superadmin_for_tenant_setup"
    super_admin_email = "superadmin_for_tenant@example.com"
    super_admin_password = "supersecretpassword"

    await create_test_user_directly(
        username=super_admin_username,
        email=super_admin_email,
        password=super_admin_password,
        role=UserRoleEnum.super_admin
    )
    super_admin_headers = await get_auth_headers(username=super_admin_username, password=super_admin_password)

    # 2. Super Admin creates a Tenant
    tenant_name = "Primary Test Tenant"
    response = await async_client.post("/tenants/", json={"name": tenant_name}, headers=super_admin_headers) # Added trailing slash
    response.raise_for_status()
    tenant = TenantResponse(**response.json())

    # 3. Create Tenant Admin for this Tenant (directly in DB for setup simplicity)
    tenant_admin_username = "test_tenant_admin"
    tenant_admin_email = "tenant_admin@example.com"
    tenant_admin_password = "tenantadminpassword"

    tenant_admin_user = await create_test_user_directly(
        username=tenant_admin_username,
        email=tenant_admin_email,
        password=tenant_admin_password,
        role=UserRoleEnum.tenant_admin,
        tenant_id=tenant.id
    )

    # 4. Get Tenant Admin Auth Headers
    tenant_admin_headers = await get_auth_headers(username=tenant_admin_username, password=tenant_admin_password)

    return tenant, tenant_admin_user, tenant_admin_headers

async def test_create_staff_by_tenant_admin(
    async_client: httpx.AsyncClient,
    tenant_and_admin_setup: Any # Fixture providing tenant, tenant_admin_user, tenant_admin_headers
):
    tenant, _, tenant_admin_headers = tenant_and_admin_setup

    staff_username = "new_picker_staff"
    staff_email = "picker@example.com"
    staff_password = "pickerpassword"

    staff_data = StaffCreate( # Defined in user_schemas
        username=staff_username,
        email=staff_email,
        password=staff_password,
        role=UserRoleEnum.picker, # Explicitly setting role for staff member
        tenant_id=tenant.id # This might be redundant if API derives from path, but good for clarity
    )

    # API: POST /tenants/{tenant_id}/staff
    # Note: The API design doc StaffCreate inherits UserCreate, role is set by logic/endpoint
    # The endpoint in API doc is /tenants/{tenant_id}/staff, body is StaffCreate (username, email, password, assigned_role)
    # Let's adjust staff_data to match the likely expectation of the endpoint if it uses a specific `assigned_role`
    # The schema StaffCreate in user_schemas.py has role, which should be fine.

    response = await async_client.post(
        f"/tenants/{tenant.id}/staff",
        json=staff_data.model_dump(), # Changed to model_dump()
        headers=tenant_admin_headers
    )

    assert response.status_code == 201
    created_staff = StaffResponse(**response.json())
    assert created_staff.username == staff_username
    assert created_staff.role == UserRoleEnum.picker
    assert created_staff.tenant_id == tenant.id

async def test_create_product_by_tenant_admin(
    async_client: httpx.AsyncClient,
    tenant_and_admin_setup: Any
):
    tenant, _, tenant_admin_headers = tenant_and_admin_setup

    product_data = ProductCreate(
        name="Test Product by Tenant Admin",
        description="A fantastic product",
        price=19.99,
        sku=f"SKU_TA_{tenant.id}_001",
        stock_quantity=100,
        # tenant_id is implicit from authenticated tenant_admin as per API Doc
    )

    response = await async_client.post(
        "/products/", # Added trailing slash, tenant_id is derived from token
        json=product_data.model_dump(mode='json'), # Changed to model_dump(mode='json')
        headers=tenant_admin_headers
    )

    assert response.status_code == 201
    created_product = ProductResponse(**response.json())
    assert created_product.name == product_data.name
    assert created_product.sku == product_data.sku
    assert created_product.tenant_id == tenant.id
