from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.models.sql_models import User # For type hinting current_admin
from app.models.sql_models import UserRole as DBUserRoleEnum # For comparison
from app.schemas.tenant_schemas import TenantCreate, TenantResponse
from app.schemas.user_schemas import StaffCreate, StaffResponse, UserRoleEnum, StaffUpdate
from app.services import tenant_service, user_service
from app.api import deps

router = APIRouter()

# Tenant Management (Super Admin)
@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(deps.get_current_active_superuser)])
def create_new_tenant(tenant: TenantCreate, db: Session = Depends(get_db)):
    db_tenant = tenant_service.get_tenant_by_name(db, name=tenant.name)
    if db_tenant:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant name already registered")
    return tenant_service.create_tenant(db=db, tenant=tenant)

@router.get("/", response_model=List[TenantResponse], dependencies=[Depends(deps.get_current_active_superuser)])
def read_all_tenants(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tenants = tenant_service.get_tenants(db, skip=skip, limit=limit)
    return tenants

@router.get("/{tenant_id}", response_model=TenantResponse)
def read_tenant_by_id(
    tenant_id: int = Path(..., title="The ID of the tenant to get"),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.can_manage_tenant) # Ensures superadmin or correct tenant_admin
):
    db_tenant = tenant_service.get_tenant_by_id(db, tenant_id=tenant_id)
    if db_tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return db_tenant

# Staff Management (Tenant Admin or Super Admin for any tenant)
@router.post("/{tenant_id}/staff", response_model=StaffResponse, status_code=status.HTTP_201_CREATED)
def create_staff_for_tenant(
    tenant_id: int, # Path param, will be automatically passed to can_manage_tenant
    staff: StaffCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.can_manage_tenant)
):
    # Validate role: staff roles can be picker, counter, or tenant_admin (if a tenant_admin creates another tenant_admin for their tenant)
    if staff.role not in [UserRoleEnum.picker, UserRoleEnum.counter, UserRoleEnum.tenant_admin]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role for staff member. Allowed roles: picker, counter, tenant_admin.")

    # Ensure the creating admin is not trying to create a super_admin
    if staff.role == UserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create super_admin via this endpoint.")

    # Check for existing username/email
    db_user_by_username = user_service.get_user_by_username(db, username=staff.username)
    if db_user_by_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    db_user_by_email = user_service.get_user_by_email(db, email=staff.email)
    if db_user_by_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    staff.tenant_id = tenant_id # Set tenant_id from path
    # User UserCreate schema (StaffCreate inherits from it) for user_service.create_user
    created_staff_user = user_service.create_user(db=db, user=staff)
    return created_staff_user

@router.get("/{tenant_id}/staff", response_model=List[StaffResponse])
def list_staff_for_tenant(
    tenant_id: int, # Path param
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.can_manage_tenant)
):
    staff_list = user_service.get_users_by_tenant(db, tenant_id=tenant_id, skip=skip, limit=limit)
    # This returns all users for the tenant. Further filtering by role (e.g., excluding 'customer') can be done here if needed.
    # For now, assuming all users attached to a tenant_id (excluding super_admins who don't have one) are staff or customers of that tenant.
    # The prompt implies "StaffResponse" so ideally we should filter for staff roles.

    # Filter for actual staff roles
    actual_staff = [user for user in staff_list if user.role in [DBUserRoleEnum.picker, DBUserRoleEnum.counter, DBUserRoleEnum.tenant_admin]]
    return actual_staff

@router.get("/{tenant_id}/staff/{user_id}", response_model=StaffResponse)
def get_staff_member(
    tenant_id: int, user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.can_manage_tenant)
):
    staff = user_service.get_user_by_id_and_tenant(db, user_id=user_id, tenant_id=tenant_id)
    if not staff or staff.role not in [DBUserRoleEnum.picker, DBUserRoleEnum.counter, DBUserRoleEnum.tenant_admin]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found in this tenant or user is not staff")
    return staff

@router.put("/{tenant_id}/staff/{user_id}", response_model=StaffResponse)
def update_staff_member_details(
    tenant_id: int, user_id: int, staff_update: StaffUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.can_manage_tenant)
):
    staff_member = user_service.get_user_by_id_and_tenant(db, user_id=user_id, tenant_id=tenant_id)
    if not staff_member or staff_member.role not in [DBUserRoleEnum.picker, DBUserRoleEnum.counter, DBUserRoleEnum.tenant_admin]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found or user is not staff")

    # Logic to update staff: is_active, role, username, email (cannot change password here)
    if staff_update.is_active is not None:
        staff_member.is_active = staff_update.is_active # type: ignore

    if staff_update.role:
        # Ensure role is a valid staff role and not super_admin
        if staff_update.role not in [UserRoleEnum.picker, UserRoleEnum.counter, UserRoleEnum.tenant_admin]:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role for staff member.")
        staff_member.role = DBUserRoleEnum[staff_update.role.value] # Convert Pydantic enum to DB enum

    if staff_update.username:
        existing_user = user_service.get_user_by_username(db, username=staff_update.username)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")
        staff_member.username = staff_update.username # type: ignore

    if staff_update.email:
        existing_user = user_service.get_user_by_email(db, email=staff_update.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already taken")
        staff_member.email = staff_update.email # type: ignore

    db.add(staff_member)
    db.commit()
    db.refresh(staff_member)
    return staff_member
