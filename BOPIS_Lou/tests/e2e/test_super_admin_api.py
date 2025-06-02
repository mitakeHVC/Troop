import pytest
import httpx
from typing import Dict, Callable, Awaitable

from app.models.sql_models import User as UserModel # For type hinting if needed
from app.schemas.user_schemas import UserRoleEnum
from app.schemas.tenant_schemas import TenantResponse

pytestmark = pytest.mark.asyncio

async def test_create_tenant_by_super_admin(
    async_client: httpx.AsyncClient,
    create_test_user_directly: Callable[..., Awaitable[UserModel]],
    get_auth_headers: Callable[..., Awaitable[Dict[str, str]]]
):
    # Create a super admin user
    super_admin_username = "test_superadmin"
    super_admin_email = "superadmin@example.com"
    super_admin_password = "supersecretpassword"

    await create_test_user_directly(
        username=super_admin_username,
        email=super_admin_email,
        password=super_admin_password,
        role=UserRoleEnum.super_admin
    )

    # Get auth headers for the super admin
    auth_headers = await get_auth_headers(username=super_admin_username, password=super_admin_password)

    # Tenant data
    tenant_name = "Test Tenant by SuperAdmin"
    tenant_data = {"name": tenant_name}

    # Make API call to create tenant
    response = await async_client.post("/tenants/", json=tenant_data, headers=auth_headers)

    # Assertions
    assert response.status_code == 201
    created_tenant = TenantResponse(**response.json())
    assert created_tenant.name == tenant_name
    assert created_tenant.id is not None

async def test_list_tenants_by_super_admin(
    async_client: httpx.AsyncClient,
    create_test_user_directly: Callable[..., Awaitable[UserModel]],
    get_auth_headers: Callable[..., Awaitable[Dict[str, str]]]
):
    # Create a super admin user (could be the same as above, but tests should be isolated if possible)
    # For simplicity here, we'll recreate or rely on previous creation if tests run sequentially in memory
    # However, best practice is for tests to be independent.
    # Let's ensure a super_admin exists for this test.
    super_admin_username = "test_superadmin_lister"
    super_admin_email = "superadmin_lister@example.com"
    super_admin_password = "supersecretpassword_lister"

    await create_test_user_directly(
        username=super_admin_username,
        email=super_admin_email,
        password=super_admin_password,
        role=UserRoleEnum.super_admin
    )
    auth_headers = await get_auth_headers(username=super_admin_username, password=super_admin_password)

    # Create a tenant first to ensure there's something to list
    tenant_name_to_list = "Tenant For Listing"
    await async_client.post("/tenants/", json={"name": tenant_name_to_list}, headers=auth_headers)

    # Make API call to list tenants
    response = await async_client.get("/tenants/", headers=auth_headers)

    # Assertions
    assert response.status_code == 200
    response_data = response.json() # This should be a list of tenant dicts
    assert isinstance(response_data, list) # Verify it's a list

    listed_tenants = [TenantResponse(**t) for t in response_data] # Iterate over the list directly
    assert any(tenant.name == tenant_name_to_list for tenant in listed_tenants)
    assert len(listed_tenants) > 0 # Ensure at least one tenant is returned (the one we created)
