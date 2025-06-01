import pytest
from sqlalchemy.orm import Session as SQLAlchemySession
from fastapi import HTTPException
import decimal # For ProductCreate price

from app.services import product_service
from app.schemas.product_schemas import ProductCreate, ProductUpdate
from app.models.sql_models import Tenant, Product # For test setup

@pytest.fixture
def test_tenant(db_session: SQLAlchemySession) -> Tenant: # Renamed to avoid conflict with other test files if tests run globally
    tenant = Tenant(name="ProductServiceTestTenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant

def test_create_product(db_session: SQLAlchemySession, test_tenant: Tenant):
    product_data = ProductCreate(name="Test Product", sku="TPS001", price=decimal.Decimal("19.99"), stock_quantity=50)
    product = product_service.create_product(db_session, product_in=product_data, tenant_id=test_tenant.id)

    assert product is not None
    assert product.name == product_data.name
    assert product.sku == product_data.sku
    assert product.tenant_id == test_tenant.id
    assert product.version == 1

def test_create_product_sku_uniqueness(db_session: SQLAlchemySession, test_tenant: Tenant):
    product_data1 = ProductCreate(name="Product SKUA", sku="UNIQUE_SKU_001", price=decimal.Decimal("10.00"), stock_quantity=10)
    product_service.create_product(db_session, product_in=product_data1, tenant_id=test_tenant.id)

    product_data2 = ProductCreate(name="Product SKUB", sku="UNIQUE_SKU_001", price=decimal.Decimal("20.00"), stock_quantity=5)
    with pytest.raises(HTTPException) as excinfo:
        product_service.create_product(db_session, product_in=product_data2, tenant_id=test_tenant.id)
    assert excinfo.value.status_code == 400
    assert "Product with SKU 'UNIQUE_SKU_001' already exists" in excinfo.value.detail

def test_update_product_optimistic_locking(db_session: SQLAlchemySession, test_tenant: Tenant):
    product_data = ProductCreate(name="Optimistic Lock Product", sku="LOCKPS001", price=decimal.Decimal("50.00"), stock_quantity=5)
    db_product = product_service.create_product(db_session, product_in=product_data, tenant_id=test_tenant.id)

    assert db_product.version == 1

    # Successful first update with correct version
    update_data_v1 = ProductUpdate(name="Lock Product V2", version=1)
    updated_product_v2 = product_service.update_product(db_session, db_product=db_product, product_in=update_data_v1)
    assert updated_product_v2.name == "Lock Product V2"
    assert updated_product_v2.version == 2

    # Try to update again with the old (stale) version=1
    update_data_stale = ProductUpdate(name="Lock Product V3 Attempt", version=1)
    # Need to use the latest instance of db_product (which is updated_product_v2) for the next update call
    with pytest.raises(HTTPException) as excinfo:
        product_service.update_product(db_session, db_product=updated_product_v2, product_in=update_data_stale)
    assert excinfo.value.status_code == 409
    assert "Product has been modified by another transaction" in excinfo.value.detail

    # Fetch the product again to ensure we have the latest version from DB before next update
    db_product_fresh_v2 = product_service.get_product_by_id(db_session, product_id=db_product.id, tenant_id=test_tenant.id)
    assert db_product_fresh_v2 is not None
    assert db_product_fresh_v2.version == 2 # Confirm version is 2

    # Successful update with the correct current version (version=2)
    update_data_v2_correct = ProductUpdate(name="Lock Product V3 Final", version=2)
    updated_product_v3 = product_service.update_product(db_session, db_product=db_product_fresh_v2, product_in=update_data_v2_correct)
    assert updated_product_v3.name == "Lock Product V3 Final"
    assert updated_product_v3.version == 3

def test_update_product_sku_uniqueness_on_update(db_session: SQLAlchemySession, test_tenant: Tenant):
    prod1_data = ProductCreate(name="ProdSKU1", sku="SKU_T_01", price=decimal.Decimal("10.00"), stock_quantity=10)
    prod1 = product_service.create_product(db_session, product_in=prod1_data, tenant_id=test_tenant.id)

    prod2_data = ProductCreate(name="ProdSKU2", sku="SKU_T_02", price=decimal.Decimal("20.00"), stock_quantity=10)
    prod2 = product_service.create_product(db_session, product_in=prod2_data, tenant_id=test_tenant.id)

    # Try to update prod2's SKU to prod1's SKU
    update_sku_to_existing = ProductUpdate(sku=prod1.sku) # type: ignore
    with pytest.raises(HTTPException) as excinfo:
        product_service.update_product(db_session, db_product=prod2, product_in=update_sku_to_existing)
    assert excinfo.value.status_code == 400
    assert f"Product with SKU '{prod1.sku}' already exists" in excinfo.value.detail # type: ignore

    # Ensure SKU can be updated to something unique
    update_sku_to_unique = ProductUpdate(sku="SKU_T_03_NEW")
    updated_prod2 = product_service.update_product(db_session, db_product=prod2, product_in=update_sku_to_unique)
    assert updated_prod2.sku == "SKU_T_03_NEW"
