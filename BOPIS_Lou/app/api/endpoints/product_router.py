"""
API router for product management.

Provides endpoints for creating, retrieving, updating, and deleting products.
Access control is based on user roles (tenant_admin, super_admin for write operations,
and flexible access for read operations including public if tenant is specified).
Endpoints are typically scoped by tenant.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime
from app.db.session import get_db
from app.models.sql_models import User, Product
from app.models.sql_models import UserRole as DBUserRoleEnum
from app.schemas.product_schemas import ProductCreate, ProductResponse, ProductUpdate
from app.services import product_service
from app.api import deps

router = APIRouter()

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_new_product(
    product_create_data: ProductCreate, # Renamed
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    """
    Create a new product for the authenticated tenant admin's tenant.
    Super_admins should use tenant-specific administrative routes for product creation.
    """
    if current_user.role == DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admins must use a dedicated admin interface or specify tenant_id explicitly for product creation within a tenant context.")

    if not current_user.tenant_id: # Should be guaranteed by get_current_active_tenant_admin if not super_admin
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin must be associated with a tenant.")

    return product_service.create_product(db=db, product_in=product_create_data, tenant_id=current_user.tenant_id)

@router.get("/", response_model=List[ProductResponse])
def list_products( # Renamed for clarity
    skip: int = 0,
    limit: int = 100,
    updated_since: Optional[datetime.datetime] = None,
    tenant_id_query: Optional[int] = Query(None, alias="tenantId", description="Specify Tenant ID to view products (required for public/general users, or for super_admin)."),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(deps.get_current_user) # Auth is optional for public listing
):
    """
    List products.
    - Public/General Users: Must provide `tenantId` query parameter.
    - Tenant Admin: Sees products for their own tenant. Can optionally use `tenantId` if it matches their own.
    - Super Admin: Must provide `tenantId` query parameter to specify which tenant's products to view.
    """
    effective_tenant_id: Optional[int] = None

    if current_user:
        if current_user.role == DBUserRoleEnum.super_admin:
            if tenant_id_query is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin must specify tenant_id via 'tenantId' query parameter to list products.")
            effective_tenant_id = tenant_id_query
        elif current_user.role == DBUserRoleEnum.tenant_admin:
            if tenant_id_query and tenant_id_query != current_user.tenant_id: # type: ignore
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin can only view their own products.")
            effective_tenant_id = current_user.tenant_id # type: ignore
        else: # Other authenticated roles (customer, picker, counter)
            if tenant_id_query is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID must be specified for product listing.")
            effective_tenant_id = tenant_id_query
    else: # Public access (no current_user)
        if tenant_id_query is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID must be specified for public product listing.")
        effective_tenant_id = tenant_id_query

    if effective_tenant_id is None:
        # This case should ideally be prevented by the logic above.
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not determine tenant context for product listing.")

    products = product_service.get_products_by_tenant(
        db, tenant_id=effective_tenant_id, skip=skip, limit=limit, updated_since=updated_since
    )
    return products

@router.get("/{product_id}", response_model=ProductResponse)
def get_product_by_id_public_or_scoped( # Renamed for clarity
    product_id: int,
    tenant_id_query: Optional[int] = Query(None, alias="tenantId", description="Specify Tenant ID if accessing as public user, general staff, or super_admin."),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(deps.get_current_user)
):
    """
    Get a specific product by its ID.
    - Public/General Users: Must provide `tenantId` query parameter.
    - Tenant Admin: Can view products from their own tenant. `tenantId` is optional, if provided must match.
    - Super Admin: Must provide `tenantId` query parameter.
    """
    effective_tenant_id: Optional[int] = None

    if current_user:
        if current_user.role == DBUserRoleEnum.tenant_admin:
            effective_tenant_id = current_user.tenant_id # type: ignore
            if tenant_id_query and tenant_id_query != effective_tenant_id:
                 raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin can only access products from their own tenant.")
        elif current_user.role == DBUserRoleEnum.super_admin:
            if not tenant_id_query:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin must specify tenant_id via 'tenantId' query parameter to view a specific product.")
            effective_tenant_id = tenant_id_query
        else: # Other authenticated roles
            if not tenant_id_query:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID must be specified to view this product.")
            effective_tenant_id = tenant_id_query
    else: # Public access
        if not tenant_id_query:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID must be specified to view this product.")
        effective_tenant_id = tenant_id_query

    if effective_tenant_id is None:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not determine tenant context for product retrieval.")

    db_product = product_service.get_product_by_id(db, product_id=product_id, tenant_id=effective_tenant_id)

    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found in the specified tenant context.")
    return db_product

@router.put("/{product_id}", response_model=ProductResponse)
def update_existing_product(
    product_id: int,
    product_update_data: ProductUpdate, # Renamed
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    """
    Update an existing product. Requires tenant_admin privileges for the product's tenant.
    Super_admins should use tenant-specific administrative routes.
    Optimistic locking is handled via the 'version' field in `product_update_data`.
    """
    effective_tenant_id: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
        # This endpoint is primarily for tenant_admins updating their own products.
        # Super_admin product updates should occur via a path that specifies the tenant.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin product updates require a specific tenant context route (e.g., /admin/tenants/{id}/products/{pid}).")

    if not current_user.tenant_id: # Ensured by deps.get_current_active_tenant_admin if not super_admin
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin must be associated with a tenant.")
    effective_tenant_id = current_user.tenant_id

    db_product = product_service.get_product_by_id(db, product_id=product_id, tenant_id=effective_tenant_id) # type: ignore
    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found in your tenant or you are not authorized.")

    return product_service.update_product(db=db, db_product=db_product, product_update_data=product_update_data) # Pass renamed var

@router.delete("/{product_id}", response_model=ProductResponse)
def delete_existing_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin)
):
    """
    Delete an existing product. Requires tenant_admin privileges for the product's tenant.
    Super_admins should use tenant-specific administrative routes.
    """
    effective_tenant_id: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin product deletion requires a specific tenant context route.")

    if not current_user.tenant_id: # Ensured by deps.get_current_active_tenant_admin if not super_admin
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin must be associated with a tenant.")
    effective_tenant_id = current_user.tenant_id

    db_product = product_service.get_product_by_id(db, product_id=product_id, tenant_id=effective_tenant_id) # type: ignore
    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found in your tenant or you are not authorized.")

    product_service.delete_product(db=db, db_product=db_product)
    # Returning the deleted object is fine, though it's transient after commit.
    # Alternatively, return a success message or status code 204.
    return db_product
