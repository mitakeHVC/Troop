"""
API router for tenant management and staff management within tenants.
- Tenant creation and listing are super_admin responsibilities.
- Staff creation and management within a tenant can be done by that tenant's admin
  or by a super_admin.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query # Added Query
from sqlalchemy.orm import Session
from typing import List, Optional # Added Optional

from app.db.session import get_db
from app.models.sql_models import User
from app.models.sql_models import UserRole as DBUserRoleEnum
from app.schemas.tenant_schemas import TenantCreate, TenantResponse
from app.schemas.user_schemas import StaffCreate, StaffResponse, UserRoleEnum as PydanticUserRoleEnum, StaffUpdate # Renamed UserRoleEnum to PydanticUserRoleEnum
from app.services import tenant_service, user_service
from app.api import deps

router = APIRouter()

# --- Tenant Management (Super Admin) ---
@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(deps.get_current_active_superuser)])
def create_new_tenant(tenant_in: TenantCreate, db: Session = Depends(get_db)): # Renamed tenant to tenant_in
    """
    Create a new tenant. Requires super_admin privileges.
    """
    db_tenant = tenant_service.get_tenant_by_name(db, name=tenant_in.name)
    if db_tenant:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant name already registered")
    return tenant_service.create_tenant(db=db, tenant_in=tenant_in) # Pass tenant_in

@router.get("/", response_model=List[TenantResponse], dependencies=[Depends(deps.get_current_active_superuser)])
def read_all_tenants(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve all tenants. Requires super_admin privileges.
    """
    tenants = tenant_service.get_tenants(db, skip=skip, limit=limit)
    return tenants

@router.get("/{tenant_id}", response_model=TenantResponse)
def read_tenant_by_id(
    tenant_id: int = Path(..., title="The ID of the tenant to get"),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.can_manage_tenant) # Ensures superadmin or admin of this specific tenant
):
    """
    Retrieve a specific tenant by ID.
    Requires super_admin or tenant_admin of the specified tenant.
    """
    db_tenant = tenant_service.get_tenant_by_id(db, tenant_id=tenant_id)
    if db_tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return db_tenant

# --- Staff Management (Tenant Admin or Super Admin for any tenant) ---
@router.post("/{tenant_id}/staff", response_model=StaffResponse, status_code=status.HTTP_201_CREATED)
def create_staff_for_tenant(
    tenant_id: int,
    staff_in: StaffCreate, # Renamed staff to staff_in
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.can_manage_tenant) # Validates current_admin can manage this tenant_id
):
    """
    Create a new staff member (picker, counter, or tenant_admin) for a specific tenant.
    Requires tenant_admin of the target tenant or super_admin.
    """
    if staff_in.role not in [PydanticUserRoleEnum.picker, PydanticUserRoleEnum.counter, PydanticUserRoleEnum.tenant_admin]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role for staff member. Allowed roles: picker, counter, tenant_admin.")
    if staff_in.role == PydanticUserRoleEnum.super_admin: # Check against Pydantic enum value
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create super_admin via this endpoint.")

    db_user_by_username = user_service.get_user_by_username(db, username=staff_in.username)
    if db_user_by_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    db_user_by_email = user_service.get_user_by_email(db, email=staff_in.email)
    if db_user_by_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    staff_in.tenant_id = tenant_id
    created_staff_user = user_service.create_user(db=db, user_in=staff_in) # Pass staff_in
    return created_staff_user

@router.get("/{tenant_id}/staff", response_model=List[StaffResponse])
def list_staff_for_tenant(
    tenant_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.can_manage_tenant) # Validates current_admin can manage this tenant_id
):
    """
    List staff members for a specific tenant.
    Requires tenant_admin of the target tenant or super_admin.
    Filters out 'customer' roles.
    """
    all_tenant_users = user_service.get_users_by_tenant(db, tenant_id=tenant_id, skip=skip, limit=limit)
    # Filter for actual staff roles (picker, counter, tenant_admin)
    staff_list = [user for user in all_tenant_users if user.role in [DBUserRoleEnum.picker, DBUserRoleEnum.counter, DBUserRoleEnum.tenant_admin]]
    return staff_list

@router.get("/{tenant_id}/staff/{user_id}", response_model=StaffResponse)
def get_staff_member_for_tenant( # Renamed for clarity
    tenant_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.can_manage_tenant) # Validates current_admin can manage this tenant_id
):
    """
    Retrieve a specific staff member from a specific tenant.
    Requires tenant_admin of the target tenant or super_admin.
    """
    staff_member = user_service.get_user_by_id_and_tenant(db, user_id=user_id, tenant_id=tenant_id)
    if not staff_member or staff_member.role not in [DBUserRoleEnum.picker, DBUserRoleEnum.counter, DBUserRoleEnum.tenant_admin]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found in this tenant or user is not staff.")
    return staff_member

@router.put("/{tenant_id}/staff/{user_id}", response_model=StaffResponse)
def update_staff_member_for_tenant( # Renamed for clarity
    tenant_id: int,
    user_id: int,
    staff_update_data: StaffUpdate, # Renamed staff_update
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.can_manage_tenant) # Validates current_admin can manage this tenant_id
):
    """
    Update a staff member's details (role, active status, username, email) for a specific tenant.
    Password changes are not handled here.
    Requires tenant_admin of the target tenant or super_admin.
    """
    staff_member_to_update = user_service.get_user_by_id_and_tenant(db, user_id=user_id, tenant_id=tenant_id)
    if not staff_member_to_update or staff_member_to_update.role not in [DBUserRoleEnum.picker, DBUserRoleEnum.counter, DBUserRoleEnum.tenant_admin]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found or user is not staff.")

    # --- Begin Update Logic (similar to user_service.update_user but for specific fields by admin) ---
    update_data_dict = staff_update_data.dict(exclude_unset=True)

    if "username" in update_data_dict:
        existing_user = user_service.get_user_by_username(db, username=update_data_dict["username"])
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken.")
        staff_member_to_update.username = update_data_dict["username"] # type: ignore

    if "email" in update_data_dict:
        existing_user = user_service.get_user_by_email(db, email=update_data_dict["email"])
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already taken.")
        staff_member_to_update.email = update_data_dict["email"] # type: ignore

    if "is_active" in update_data_dict:
        staff_member_to_update.is_active = update_data_dict["is_active"] # type: ignore

    if "role" in update_data_dict:
        new_role_value = update_data_dict["role"]
        if new_role_value not in [PydanticUserRoleEnum.picker, PydanticUserRoleEnum.counter, PydanticUserRoleEnum.tenant_admin]:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role assigned to staff member.")
        if new_role_value == PydanticUserRoleEnum.super_admin:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot assign super_admin role via this endpoint.")
        staff_member_to_update.role = DBUserRoleEnum[new_role_value.value] # Convert Pydantic enum to DB enum

    db.add(staff_member_to_update)
    db.commit()
    db.refresh(staff_member_to_update)
    return staff_member_to_update
