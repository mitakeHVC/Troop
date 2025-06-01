import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as SQLAlchemySession
from typing import Optional, Dict, Any # For type hinting

from app.models.sql_models import Tenant, User
from app.models.sql_models import UserRole as DBUserRoleEnum
from app.core.security import create_access_token, get_password_hash
from app.schemas.user_schemas import UserRoleEnum as PydanticUserRoleEnum # For request payloads

# Helper to create user (can be in conftest.py or shared test utils)
def create_test_user_for_tenants(db_session: SQLAlchemySession, username: str, role: DBUserRoleEnum, tenant_id: Optional[int] = None, email_suffix: str = "@example.com") -> User:
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
def get_auth_headers_for_tenants(user_id: int, role: str, tenant_id: Optional[int]) -> Dict[str, str]:
    token = create_access_token(subject=str(user_id), role=role, tenant_id=tenant_id)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function")
def super_admin_headers(db_session: SQLAlchemySession) -> Dict[str, str]:
    super_admin = create_test_user_for_tenants(db_session, f"super_{id(db_session)}", DBUserRoleEnum.super_admin)
    return get_auth_headers_for_tenants(super_admin.id, super_admin.role.value, super_admin.tenant_id)

@pytest.fixture(scope="function")
def basic_tenant(db_session: SQLAlchemySession) -> Tenant:
    tenant = Tenant(name=f"BasicTenant_{id(db_session)}")
    db_session.add(tenant); db_session.commit(); db_session.refresh(tenant)
    return tenant

def test_create_tenant_rbac_and_validation(client: TestClient, db_session: SQLAlchemySession, super_admin_headers: Dict[str, str]):
    # Attempt by non-superadmin (e.g. customer)
    customer = create_test_user_for_tenants(db_session, f"tenantcust_{id(db_session)}", DBUserRoleEnum.customer)
    customer_headers = get_auth_headers_for_tenants(customer.id, customer.role.value, customer.tenant_id)
    tenant_data_fail = {"name": "Fail Tenant by Customer"}
    response_fail_auth = client.post("/tenants/", json=tenant_data_fail, headers=customer_headers)
    assert response_fail_auth.status_code == 403 # Forbidden

    # Success by superadmin
    tenant_data_ok = {"name": f"SuperTenant_{id(db_session)}"}
    response_ok = client.post("/tenants/", json=tenant_data_ok, headers=super_admin_headers)
    assert response_ok.status_code == 201, response_ok.text
    created_tenant = response_ok.json()
    assert created_tenant["name"] == tenant_data_ok["name"]
    tenant_id = created_tenant["id"]

    # Validation error (e.g. missing name)
    response_validation_err = client.post("/tenants/", json={}, headers=super_admin_headers)
    assert response_validation_err.status_code == 422 # Unprocessable Entity

    # Duplicate name
    response_dup_name = client.post("/tenants/", json=tenant_data_ok, headers=super_admin_headers)
    assert response_dup_name.status_code == 400
    assert "Tenant name already registered" in response_dup_name.json()["detail"]

    # Get created tenant
    response_get_tenant = client.get(f"/tenants/{tenant_id}", headers=super_admin_headers)
    assert response_get_tenant.status_code == 200
    assert response_get_tenant.json()["name"] == tenant_data_ok["name"]

    # List tenants
    response_list_tenants = client.get("/tenants/", headers=super_admin_headers)
    assert response_list_tenants.status_code == 200
    tenants_list = response_list_tenants.json()
    assert isinstance(tenants_list, list)
    assert any(t["id"] == tenant_id for t in tenants_list)


def test_staff_creation_and_rbac_in_tenant(client: TestClient, db_session: SQLAlchemySession, super_admin_headers: Dict[str, str], basic_tenant: Tenant):
    tenant_id = basic_tenant.id

    # Create tenant admin for this tenant (can be done by superadmin)
    t_admin_user = create_test_user_for_tenants(db_session, f"staffadmin_{id(db_session)}", DBUserRoleEnum.tenant_admin, tenant_id)
    t_admin_headers = get_auth_headers_for_tenants(t_admin_user.id, t_admin_user.role.value, t_admin_user.tenant_id)

    # Tenant admin creates a picker
    picker_data = {
        "username": f"newpicker_{id(db_session)}",
        "email": f"picker_{id(db_session)}@staff.com",
        "password": "staffpw",
        "role": PydanticUserRoleEnum.picker.value # Use Pydantic enum value for request
    }
    response_create_picker = client.post(f"/tenants/{tenant_id}/staff", json=picker_data, headers=t_admin_headers)
    assert response_create_picker.status_code == 201, response_create_picker.text
    created_picker = response_create_picker.json()
    assert created_picker["username"] == picker_data["username"]
    assert created_picker["role"] == PydanticUserRoleEnum.picker.value # Response uses Pydantic enum
    assert created_picker["tenant_id"] == tenant_id
    picker_id = created_picker["id"]

    # Tenant admin lists staff for their tenant
    response_list_staff = client.get(f"/tenants/{tenant_id}/staff", headers=t_admin_headers)
    assert response_list_staff.status_code == 200, response_list_staff.text
    staff_list = response_list_staff.json()
    assert isinstance(staff_list, list)
    assert any(s["id"] == picker_id for s in staff_list)
    # Ensure only staff roles are listed (e.g. no customers)
    for staff_member in staff_list:
        assert staff_member["role"] in [PydanticUserRoleEnum.picker.value, PydanticUserRoleEnum.counter.value, PydanticUserRoleEnum.tenant_admin.value]


    # Attempt by tenant admin of another tenant to create staff (should fail)
    other_tenant = Tenant(name=f"OtherStaffTenant_{id(db_session)}"); db_session.add(other_tenant); db_session.commit(); db_session.refresh(other_tenant)

    # t_admin_headers are for 'basic_tenant', trying to operate on 'other_tenant'
    response_fail_auth_staff = client.post(f"/tenants/{other_tenant.id}/staff", json=picker_data, headers=t_admin_headers)
    assert response_fail_auth_staff.status_code == 403 # Forbidden by can_manage_tenant dependency
    assert "Not authorized to manage this tenant's resources" in response_fail_auth_staff.json()["detail"]

    # Super admin creates staff for basic_tenant
    counter_data_sa = {
        "username": f"counter_sa_{id(db_session)}",
        "email": f"counter_sa_{id(db_session)}@staff.com",
        "password": "staffpw",
        "role": PydanticUserRoleEnum.counter.value
    }
    # The current /tenants/{tenant_id}/staff endpoint's deps.can_manage_tenant allows SA.
    response_sa_create_staff = client.post(f"/tenants/{tenant_id}/staff", json=counter_data_sa, headers=super_admin_headers)
    assert response_sa_create_staff.status_code == 201, response_sa_create_staff.text
    assert response_sa_create_staff.json()["tenant_id"] == tenant_id
    assert response_sa_create_staff.json()["role"] == PydanticUserRoleEnum.counter.value

    # Test staff update (e.g. change role from picker to counter by tenant admin)
    update_staff_data = {"role": PydanticUserRoleEnum.counter.value, "is_active": False}
    response_update_staff = client.put(f"/tenants/{tenant_id}/staff/{picker_id}", json=update_staff_data, headers=t_admin_headers)
    assert response_update_staff.status_code == 200, response_update_staff.text
    updated_staff = response_update_staff.json()
    assert updated_staff["role"] == PydanticUserRoleEnum.counter.value
    assert updated_staff["is_active"] is False
