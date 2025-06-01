import pytest # Added pytest import
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as SQLAlchemySession
from typing import Optional # Added Optional for type hinting

from app.core.security import create_access_token, get_password_hash
from app.models.sql_models import User, Tenant, Product # Added Product model
from app.models.sql_models import UserRole as DBUserRoleEnum

# Helper function to generate auth headers
def get_auth_headers(user_id: int, role: str, tenant_id: Optional[int]) -> dict:
    token = create_access_token(subject=str(user_id), role=role, tenant_id=tenant_id)
    return {"Authorization": f"Bearer {token}"}

# Helper to create a user with a specific role and tenant_id for RBAC tests
def create_test_user(db_session: SQLAlchemySession, username: str, role: DBUserRoleEnum, tenant_id: Optional[int] = None, email_suffix: str = "@example.com") -> User:
    user = User(
        username=username,
        email=f"{username}{email_suffix}",
        password_hash=get_password_hash("testpassword"),
        role=role,
        tenant_id=tenant_id,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

# Fixture for a tenant and its admin (can be defined in conftest.py or here)
@pytest.fixture
def tenant_and_admin_for_products(db_session: SQLAlchemySession):
    tenant = Tenant(name=f"ProdTestTenant_{id(db_session)}") # Unique name for tenant
    db_session.add(tenant)
    db_session.commit(); db_session.refresh(tenant)
    admin = create_test_user(db_session, f"prodadmin_{id(db_session)}", DBUserRoleEnum.tenant_admin, tenant.id)
    return tenant, admin


def test_create_and_get_product_as_tenant_admin(client: TestClient, db_session: SQLAlchemySession, tenant_and_admin_for_products):
    test_tenant, admin_user = tenant_and_admin_for_products

    headers = get_auth_headers(admin_user.id, admin_user.role.value, admin_user.tenant_id)

    # 4. Create Product
    product_data = {
        "name": "Test API Product",
        "description": "A product for API testing",
        "price": 12.99,
        "sku": f"TESTAPISKU_{id(db_session)}", # Unique SKU
        "stock_quantity": 50
    }
    response_create = client.post("/products/", json=product_data, headers=headers)
    assert response_create.status_code == 201, response_create.text
    created_product = response_create.json()
    assert created_product["name"] == product_data["name"]
    assert created_product["sku"] == product_data["sku"]
    # Price comparison needs care due to float vs Decimal. Pydantic usually returns string for Decimal.
    assert float(created_product["price"]) == product_data["price"]
    product_id = created_product["id"]

    # 5. Get Product by ID (as tenant admin)
    response_get = client.get(f"/products/{product_id}", headers=headers) # This endpoint implicitly uses current_user.tenant_id
    assert response_get.status_code == 200, response_get.text
    retrieved_product = response_get.json()
    assert retrieved_product["name"] == product_data["name"]
    assert retrieved_product["id"] == product_id

    # 6. List Products for Tenant (as tenant admin)
    # This endpoint for /products/ uses current_user.tenant_id implicitly
    response_list = client.get("/products/", headers=headers)
    assert response_list.status_code == 200, response_list.text
    products_list = response_list.json()
    assert isinstance(products_list, list)
    assert any(p["id"] == product_id for p in products_list)

    # 7. Test Get Product by ID (publicly, by providing tenantId query param)
    response_get_public = client.get(f"/products/{product_id}?tenantId={test_tenant.id}")
    assert response_get_public.status_code == 200, response_get_public.text
    retrieved_product_public = response_get_public.json()
    assert retrieved_product_public["id"] == product_id
    assert retrieved_product_public["name"] == product_data["name"]

    # 8. Test List Products (publicly, by providing tenantId query param)
    response_list_public = client.get(f"/products/?tenantId={test_tenant.id}")
    assert response_list_public.status_code == 200, response_list_public.text
    products_list_public = response_list_public.json()
    assert isinstance(products_list_public, list)
    assert any(p["id"] == product_id for p in products_list_public)

    # 9. Test Optimistic Locking (Update Product)
    update_data_v1 = {
        "name": "Updated Test API Product",
        "stock_quantity": 40,
        "version": created_product["version"]
    }
    response_update_v1 = client.put(f"/products/{product_id}", json=update_data_v1, headers=headers)
    assert response_update_v1.status_code == 200, response_update_v1.text
    updated_product_v1 = response_update_v1.json()
    assert updated_product_v1["name"] == update_data_v1["name"]
    assert updated_product_v1["stock_quantity"] == update_data_v1["stock_quantity"]
    assert updated_product_v1["version"] == created_product["version"] + 1

    update_data_stale_version = {
        "name": "Attempted Update with Stale Version",
        "stock_quantity": 30,
        "version": created_product["version"]
    }
    response_update_stale = client.put(f"/products/{product_id}", json=update_data_stale_version, headers=headers)
    assert response_update_stale.status_code == 409, response_update_stale.text
    assert "Product has been modified" in response_update_stale.text


# --- RBAC and Validation Tests ---
def test_product_creation_rbac(client: TestClient, db_session: SQLAlchemySession, tenant_and_admin_for_products):
    tenant1, _ = tenant_and_admin_for_products

    customer_user = create_test_user(db_session, f"prodcust_{id(db_session)}", DBUserRoleEnum.customer, tenant1.id)
    customer_headers = get_auth_headers(customer_user.id, customer_user.role.value, customer_user.tenant_id)

    product_data = {"name": "CustProd", "price": 1.00, "sku": f"CUSTSKU_{id(db_session)}", "stock_quantity": 1}
    response = client.post("/products/", json=product_data, headers=customer_headers)
    assert response.status_code == 403

def test_product_modification_other_tenant_admin(client: TestClient, db_session: SQLAlchemySession, tenant_and_admin_for_products):
    tenant1, admin1 = tenant_and_admin_for_products
    admin1_headers = get_auth_headers(admin1.id, admin1.role.value, admin1.tenant_id)

    product_data = {"name": "T1 Prod", "price": 10.0, "sku": f"T1SKU_{id(db_session)}", "stock_quantity": 10}
    response = client.post("/products/", json=product_data, headers=admin1_headers)
    assert response.status_code == 201
    t1_product_id = response.json()["id"]

    tenant2 = Tenant(name=f"OtherTenantProd_{id(db_session)}"); db_session.add(tenant2); db_session.commit(); db_session.refresh(tenant2)
    admin2 = create_test_user(db_session, f"otherprodadmin_{id(db_session)}", DBUserRoleEnum.tenant_admin, tenant2.id)
    admin2_headers = get_auth_headers(admin2.id, admin2.role.value, admin2.tenant_id)

    update_data = {"name": "Updated by Admin2", "version": 1} # Assuming version is 1
    # Admin2 (from tenant2) tries to update product in tenant1
    # The product router's PUT endpoint uses get_current_active_tenant_admin, which scopes product fetch to admin2's tenant_id.
    # So, it should result in a 404 if product_service.get_product_by_id can't find it under admin2's tenant.
    # If the product_id was global and found, then a 403 might occur due to ownership check.
    # Given current product router logic for PUT: it fetches product using current_user's tenant_id.
    response = client.put(f"/products/{t1_product_id}", json=update_data, headers=admin2_headers)
    assert response.status_code == 404 # Because product t1_product_id won't be found under admin2's tenant_id

def test_product_creation_validation_error(client: TestClient, db_session: SQLAlchemySession, tenant_and_admin_for_products):
    _, admin = tenant_and_admin_for_products
    admin_headers = get_auth_headers(admin.id, admin.role.value, admin.tenant_id)

    # Invalid price type, missing stock_quantity (though it has a default in schema)
    invalid_product_data = {"name": "Valid Name", "price": "not-a-price-number", "sku": f"VALIDSKU_{id(db_session)}"}
    response = client.post("/products/", json=invalid_product_data, headers=admin_headers)
    assert response.status_code == 422 # Unprocessable Entity from Pydantic

    # Missing name
    invalid_product_data_no_name = {"price": 10.99, "sku": f"NONAMESKU_{id(db_session)}", "stock_quantity":10}
    response_no_name = client.post("/products/", json=invalid_product_data_no_name, headers=admin_headers)
    assert response_no_name.status_code == 422

    # SKU already exists (test from ProductService is more direct, this is API level)
    valid_sku = f"DUPSKU_API_{id(db_session)}"
    client.post("/products/", json={"name":"Prod A", "price":1.0, "sku":valid_sku, "stock_quantity":1}, headers=admin_headers)
    response_dup_sku = client.post("/products/", json={"name":"Prod B", "price":2.0, "sku":valid_sku, "stock_quantity":1}, headers=admin_headers)
    assert response_dup_sku.status_code == 400 # From product_service HTTPException for duplicate SKU
    assert "already exists" in response_dup_sku.json()["detail"]

def test_product_update_optimistic_locking_api(client: TestClient, db_session: SQLAlchemySession, tenant_and_admin_for_products):
    # This is already covered by test_create_and_get_product_as_tenant_admin's step 9.
    # Re-affirming it here as a separate test.
    _, admin = tenant_and_admin_for_products
    admin_headers = get_auth_headers(admin.id, admin.role.value, admin.tenant_id)

    product_data = {"name": "LockAPI Prod", "price": 20.0, "sku": f"LOCKAPI_SKU_{id(db_session)}", "stock_quantity": 5}
    response_create = client.post("/products/", json=product_data, headers=admin_headers)
    assert response_create.status_code == 201
    created_prod = response_create.json()
    product_id = created_prod["id"]
    assert created_prod["version"] == 1

    update1_data = {"name": "LockAPI Prod v2", "stock_quantity": 4, "version": 1}
    response_update1 = client.put(f"/products/{product_id}", json=update1_data, headers=admin_headers)
    assert response_update1.status_code == 200
    assert response_update1.json()["version"] == 2
    assert response_update1.json()["stock_quantity"] == 4

    update_stale_data = {"name": "LockAPI Prod v3", "stock_quantity": 3, "version": 1} # Stale version
    response_update_stale = client.put(f"/products/{product_id}", json=update_stale_data, headers=admin_headers)
    assert response_update_stale.status_code == 409
    assert "Product has been modified" in response_update_stale.json()["detail"]
