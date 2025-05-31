from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as SQLAlchemySession
from app.core.security import create_access_token, get_password_hash # Added get_password_hash
from app.models.sql_models import User, Tenant # UserRole is part of User model or can be imported separately
from app.models.sql_models import UserRole as DBUserRoleEnum # Import DB enum for role assignment
# from app.schemas.user_schemas import UserCreate # Not directly used if creating User model instance

def test_create_and_get_product_as_tenant_admin(client: TestClient, db_session: SQLAlchemySession):
    # 1. Create a test tenant
    test_tenant = Tenant(name="Test Tenant for Products API")
    db_session.add(test_tenant)
    db_session.commit()
    db_session.refresh(test_tenant)

    # 2. Create a test tenant_admin for this tenant
    admin_username = "productadmin_api"
    admin_email = "productadmin_api@example.com"
    admin_password = "password"

    admin_user = User(
        username=admin_username,
        email=admin_email,
        password_hash=get_password_hash(admin_password),
        role=DBUserRoleEnum.tenant_admin, # Use the DB enum directly
        tenant_id=test_tenant.id,
        is_active=True
    )
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(admin_user)

    # 3. Generate token for this tenant_admin
    admin_token = create_access_token(
        subject=str(admin_user.id),
        role=admin_user.role.value, # Pass enum value (string)
        tenant_id=admin_user.tenant_id
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 4. Create Product
    product_data = {
        "name": "Test API Product",
        "description": "A product for API testing",
        "price": 12.99, # Ensure this is passed in a way Pydantic can handle for Decimal
        "sku": "TESTAPISKU001",
        "stock_quantity": 50
    }
    # FastAPI/Pydantic will convert float 12.99 to Decimal if schema field is Decimal.
    response_create = client.post("/products/", json=product_data, headers=headers)
    assert response_create.status_code == 201, response_create.text
    created_product = response_create.json()
    assert created_product["name"] == product_data["name"]
    assert created_product["sku"] == product_data["sku"]
    assert created_product["price"] == product_data["price"] # Pydantic should handle float to Decimal string
    product_id = created_product["id"]

    # 5. Get Product by ID (as tenant admin)
    response_get = client.get(f"/products/{product_id}", headers=headers)
    assert response_get.status_code == 200, response_get.text
    retrieved_product = response_get.json()
    assert retrieved_product["name"] == product_data["name"]
    assert retrieved_product["id"] == product_id

    # 6. List Products for Tenant (as tenant admin)
    response_list = client.get("/products/", headers=headers)
    assert response_list.status_code == 200, response_list.text
    products_list = response_list.json()
    assert isinstance(products_list, list)
    assert any(p["id"] == product_id for p in products_list) # Check if our product is in the list

    # 7. Test Get Product by ID (publicly, by providing tenantId query param)
    # The /products/{product_id} endpoint in product_router.py was modified to allow this.
    response_get_public = client.get(f"/products/{product_id}?tenantId={test_tenant.id}") # No auth header
    assert response_get_public.status_code == 200, response_get_public.text
    retrieved_product_public = response_get_public.json()
    assert retrieved_product_public["id"] == product_id
    assert retrieved_product_public["name"] == product_data["name"]

    # 8. Test List Products (publicly, by providing tenantId query param)
    response_list_public = client.get(f"/products/?tenantId={test_tenant.id}") # No auth header
    assert response_list_public.status_code == 200, response_list_public.text
    products_list_public = response_list_public.json()
    assert isinstance(products_list_public, list)
    assert any(p["id"] == product_id for p in products_list_public)

    # 9. Test Optimistic Locking (Update Product)
    update_data_v1 = {
        "name": "Updated Test API Product",
        "stock_quantity": 40,
        "version": created_product["version"] # Pass current version
    }
    response_update_v1 = client.put(f"/products/{product_id}", json=update_data_v1, headers=headers)
    assert response_update_v1.status_code == 200, response_update_v1.text
    updated_product_v1 = response_update_v1.json()
    assert updated_product_v1["name"] == update_data_v1["name"]
    assert updated_product_v1["stock_quantity"] == update_data_v1["stock_quantity"]
    assert updated_product_v1["version"] == created_product["version"] + 1

    # Attempt update with stale version
    update_data_stale_version = {
        "name": "Attempted Update with Stale Version",
        "stock_quantity": 30,
        "version": created_product["version"] # Original version, now stale
    }
    response_update_stale = client.put(f"/products/{product_id}", json=update_data_stale_version, headers=headers)
    assert response_update_stale.status_code == 409, response_update_stale.text # Conflict
    assert "Product has been modified" in response_update_stale.text
