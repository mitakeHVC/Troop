"""
Service layer for product management.

This module handles the business logic for creating, retrieving,
updating, and deleting products, including stock management and
optimistic locking.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.models.sql_models import Product
from app.schemas.product_schemas import ProductCreate, ProductUpdate
from fastapi import HTTPException, status
import datetime # Keep for updated_since type hint

def get_product_by_id(db: Session, product_id: int, tenant_id: int) -> Optional[Product]:
    """
    Retrieves a product by its ID and tenant ID.

    Args:
        db: SQLAlchemy database session.
        product_id: ID of the product to retrieve.
        tenant_id: ID of the tenant to which the product belongs.

    Returns:
        The Product object if found, else None.
    """
    return db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant_id).first()

def get_product_by_sku_and_tenant(db: Session, sku: str, tenant_id: int) -> Optional[Product]:
    """
    Retrieves a product by its SKU and tenant ID.

    Args:
        db: SQLAlchemy database session.
        sku: SKU of the product.
        tenant_id: ID of the tenant.

    Returns:
        The Product object if found, else None.
    """
    return db.query(Product).filter(Product.sku == sku, Product.tenant_id == tenant_id).first()

def get_products_by_tenant(
    db: Session,
    tenant_id: int,
    skip: int = 0,
    limit: int = 100,
    updated_since: Optional[datetime.datetime] = None
) -> List[Product]:
    """
    Retrieves a list of products for a given tenant, with optional pagination and date filtering.

    Args:
        db: SQLAlchemy database session.
        tenant_id: ID of the tenant.
        skip: Number of records to skip (for pagination).
        limit: Maximum number of records to return (for pagination).
        updated_since: If provided, only return products updated at or after this timestamp.

    Returns:
        A list of Product objects.
    """
    query = db.query(Product).filter(Product.tenant_id == tenant_id)
    if updated_since:
        query = query.filter(Product.updated_at >= updated_since)
    return query.order_by(Product.id).offset(skip).limit(limit).all() # Added order_by for consistent pagination

def create_product(db: Session, product_create_data: ProductCreate, tenant_id: int) -> Product:
    """
    Creates a new product for a tenant.

    Args:
        db: SQLAlchemy database session.
        product_create_data: Pydantic schema with product creation data.
        tenant_id: ID of the tenant to associate the product with.

    Raises:
        HTTPException (400): If a product with the same SKU already exists for the tenant.

    Returns:
        The newly created Product object.
    """
    existing_product_sku = get_product_by_sku_and_tenant(db, sku=product_create_data.sku, tenant_id=tenant_id)
    if existing_product_sku:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product with SKU '{product_create_data.sku}' already exists for this tenant.")

    db_product = Product(
        **product_create_data.dict(),
        tenant_id=tenant_id,
        version=1, # Initial version
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def update_product(db: Session, db_product: Product, product_update_data: ProductUpdate) -> Product:
    """
    Updates an existing product. Handles optimistic locking via 'version' field.
    Note: Direct stock updates via this general function are possible but less controlled
    than using dedicated stock adjustment functions like `decrement_stock`.

    Args:
        db: SQLAlchemy database session.
        db_product: The existing Product ORM instance to update.
        product_update_data: Pydantic schema with product update data.

    Raises:
        HTTPException (409): If optimistic lock version mismatch.
        HTTPException (400): If trying to update SKU to one that already exists for another product.

    Returns:
        The updated Product object.
    """
    update_data = product_update_data.dict(exclude_unset=True)

    if product_update_data.version is not None:
        if db_product.version != product_update_data.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Product has been modified by another transaction. Please refresh and try again.",
            )
        # TODO: Revisit version increment logic for general updates.
        # Ideally, version increments only for significant changes or if stock is modified.
        # If stock_quantity is part of update_data, it implies an override and version should increment.
        # If other fields are updated and version check passes, version should also increment.
        db_product.version += 1 # type: ignore

    for field, value in update_data.items():
        if field != 'version': # Version is handled by incrementing above
            setattr(db_product, field, value)

    if 'sku' in update_data and update_data['sku'] != db_product.sku:
         existing_product_sku = get_product_by_sku_and_tenant(db, sku=update_data['sku'], tenant_id=db_product.tenant_id) # type: ignore
         if existing_product_sku and existing_product_sku.id != db_product.id :
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product with SKU '{update_data['sku']}' already exists for this tenant.")

    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def delete_product(db: Session, db_product: Product) -> Product:
    """
    Deletes a product. (Currently hard delete).

    Args:
        db: SQLAlchemy database session.
        db_product: The Product ORM instance to delete.

    Returns:
        The deleted Product object (transient after commit).
    """
    db.delete(db_product)
    db.commit()
    return db_product


def decrement_stock(db: Session, product_id: int, quantity: int, tenant_id: int, expected_version: Optional[int] = None) -> Product:
    """
    Decrements the stock of a product, with optional optimistic locking.
    This function flushes the session to update the product state within the
    current transaction but does NOT commit. The commit should be handled
    by the calling service to ensure atomicity of the overall operation.

    Args:
        db: SQLAlchemy database session.
        product_id: ID of the product to update.
        quantity: Amount to decrement stock by.
        tenant_id: ID of the tenant to which the product belongs.
        expected_version: Optional. If provided, checks against product's current version.

    Raises:
        HTTPException (404): If product not found.
        HTTPException (409): If optimistic lock version mismatch.
        HTTPException (400): If insufficient stock.

    Returns:
        The updated Product object (after flush and refresh).
    """
    db_product = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant_id).first()
    if not db_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found in tenant {tenant_id} for stock decrement.")

    if expected_version is not None and db_product.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stock update conflict for product {db_product.name}. Data may be stale. Expected version {expected_version}, found {db_product.version}.",
        )

    if db_product.stock_quantity < quantity: # type: ignore
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient stock for product {db_product.name}. Available: {db_product.stock_quantity}, Requested: {quantity}",
        )

    db_product.stock_quantity -= quantity # type: ignore
    db_product.version += 1 # type: ignore

    db.add(db_product)
    db.flush()
    db.refresh(db_product)
    return db_product
