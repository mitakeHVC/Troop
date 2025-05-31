from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime # Required for Optional[datetime.datetime]
from app.db.session import get_db
from app.models.sql_models import User, Product, UserRole as DBUserRoleEnum # User for current_user type hint
from app.schemas.product_schemas import ProductCreate, ProductResponse, ProductUpdate
from app.services import product_service
from app.api import deps

router = APIRouter()

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_new_product(
    product_in: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin) # Ensures user is tenant_admin or super_admin
):
    tenant_id_for_creation = None
    if current_user.role == DBUserRoleEnum.super_admin:
        # Super_admin MUST provide tenant_id in an admin-specific way, not covered by this endpoint.
        # Or, if product_in schema had an optional tenant_id for super_admin use.
        # For now, this endpoint is best suited for tenant_admins creating for their own tenant.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admins must use a dedicated admin interface or specify tenant_id explicitly for product creation.")

    if not current_user.tenant_id:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin must be associated with a tenant.")
    tenant_id_for_creation = current_user.tenant_id

    return product_service.create_product(db=db, product_in=product_in, tenant_id=tenant_id_for_creation)

@router.get("/", response_model=List[ProductResponse])
def read_products_for_tenant_or_public( # Renamed for clarity
    skip: int = 0,
    limit: int = 100,
    updated_since: Optional[datetime.datetime] = None,
    # For tenant admin/superuser to query specific tenant products:
    tenant_id_query: Optional[int] = Query(None, alias="tenantId"), # For superuser to specify tenant
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(deps.get_current_user) # Optional auth: public can view, admin sees more/specifics
):
    # This endpoint can serve multiple purposes:
    # 1. Public listing (current_user is None or customer) - requires a tenant_id_query
    # 2. Tenant admin listing their own products (current_user is tenant_admin)
    # 3. Super admin listing products for a specific tenant (current_user is super_admin, tenant_id_query is used)

    effective_tenant_id: Optional[int] = None

    if current_user:
        if current_user.role == DBUserRoleEnum.super_admin:
            if tenant_id_query is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin must specify tenant_id via 'tenantId' query parameter to list products.")
            effective_tenant_id = tenant_id_query
        elif current_user.role == DBUserRoleEnum.tenant_admin:
            if tenant_id_query and tenant_id_query != current_user.tenant_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin can only view their own products.")
            effective_tenant_id = current_user.tenant_id
        else: # Other authenticated users (e.g. customer, picker, counter)
            if tenant_id_query is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID must be specified for product listing.")
            effective_tenant_id = tenant_id_query # They view products of a specified tenant
    else: # Public access
        if tenant_id_query is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID must be specified for public product listing.")
        effective_tenant_id = tenant_id_query

    if effective_tenant_id is None: # Should not happen if logic above is correct
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not determine tenant for product listing.")

    products = product_service.get_products_by_tenant(
        db, tenant_id=effective_tenant_id, skip=skip, limit=limit, updated_since=updated_since
    )
    return products

@router.get("/{product_id}", response_model=ProductResponse)
def read_product_by_id(
    product_id: int,
    # tenant_id can be passed as query for public/general access to specific product
    tenant_id_query: Optional[int] = Query(None, alias="tenantId"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(deps.get_current_user) # Optional auth
):
    # If user is authenticated and is a tenant_admin, they can only get products from their tenant.
    # If user is super_admin, they can get any product if they also provide tenant_id_query.
    # If user is public/other, they MUST provide tenant_id_query.

    db_product: Optional[Product] = None
    effective_tenant_id: Optional[int] = None

    if current_user:
        if current_user.role == DBUserRoleEnum.tenant_admin:
            effective_tenant_id = current_user.tenant_id
            if tenant_id_query and tenant_id_query != effective_tenant_id: # If they pass tenant_id, it must match theirs
                 raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin can only access products from their own tenant.")
        elif current_user.role == DBUserRoleEnum.super_admin:
            if not tenant_id_query:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin must specify tenant_id via 'tenantId' query parameter.")
            effective_tenant_id = tenant_id_query
        else: # Customer or other staff
            if not tenant_id_query:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID must be specified to view this product.")
            effective_tenant_id = tenant_id_query
    else: # Public
        if not tenant_id_query:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID must be specified to view this product.")
        effective_tenant_id = tenant_id_query

    if effective_tenant_id is None:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not determine tenant for product retrieval.")

    db_product = product_service.get_product_by_id(db, product_id=product_id, tenant_id=effective_tenant_id)

    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found in the specified tenant")
    return db_product

@router.put("/{product_id}", response_model=ProductResponse)
def update_existing_product(
    product_id: int,
    product_in: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin) # Only tenant_admin or super_admin can update
):
    effective_tenant_id: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
        # Super_admin would need to specify which tenant's product they are updating.
        # This could be by ensuring product_id is globally unique and fetching tenant_id from product,
        # or by requiring tenant_id in path/query. For this endpoint, let's assume product_id implies tenant context
        # if fetched first, or super_admin needs a different interface.
        # For now, let's assume super_admin cannot use this unless product_in has tenant_id and service handles it.
        # Simplest: restrict to tenant_admin of that product.
        # To make it work for super_admin, we'd need to load product first, then check its tenant_id.
        # This dependency (get_current_active_tenant_admin) already scopes for tenant_admin.
        # Let's ensure that the product belongs to the admin's tenant.
        if not current_user.tenant_id: # Super_admin case, not directly associated with one tenant from token
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin must operate on a product within a specific tenant context (e.g., /tenants/{id}/products/{pid}).")
        effective_tenant_id = current_user.tenant_id # This is for tenant_admin
    else: # Must be tenant_admin
        effective_tenant_id = current_user.tenant_id


    db_product = product_service.get_product_by_id(db, product_id=product_id, tenant_id=effective_tenant_id) # type: ignore
    if db_product is None:
        # If super_admin, they might be trying to update a product from another tenant.
        # A better approach for SA would be /admin/products/{global_product_id} or /tenants/{tid}/products/{pid}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found in your tenant or you are not authorized.")

    # If super_admin, and they are allowed to update ANY product (once found),
    # the get_current_active_tenant_admin dependency might be too restrictive.
    # Let's assume for this router, actions are scoped to current_user.tenant_id if user is tenant_admin.
    # Super_admin use of these specific endpoints is tricky without explicit tenant_id in path.
    # The current deps.get_current_active_tenant_admin implies current_user.tenant_id exists if not super_admin.
    # This is simpler if we consider /products to be implicitly for current_user's tenant.

    return product_service.update_product(db=db, db_product=db_product, product_in=product_in)

@router.delete("/{product_id}", response_model=ProductResponse)
def delete_existing_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_tenant_admin) # Only tenant_admin or super_admin
):
    # Similar scoping logic as PUT
    effective_tenant_id: Optional[int] = None
    if current_user.role == DBUserRoleEnum.super_admin:
        if not current_user.tenant_id: # Placeholder for future logic where SA might specify tenant
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin must operate on a product within a specific tenant context.")
        effective_tenant_id = current_user.tenant_id
    else: # Must be tenant_admin
        effective_tenant_id = current_user.tenant_id

    db_product = product_service.get_product_by_id(db, product_id=product_id, tenant_id=effective_tenant_id) # type: ignore
    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found in your tenant or you are not authorized.")

    product_service.delete_product(db=db, db_product=db_product)
    return db_product # Return deleted product (or a success message)
