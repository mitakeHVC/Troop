from sqlalchemy.orm import Session
from sqlalchemy import func # For func.now()
from typing import List, Optional
from app.models.sql_models import Product
from app.schemas.product_schemas import ProductCreate, ProductUpdate
from fastapi import HTTPException, status
import datetime

def get_product_by_id(db: Session, product_id: int, tenant_id: int) -> Optional[Product]:
    return db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant_id).first()

def get_product_by_sku_and_tenant(db: Session, sku: str, tenant_id: int) -> Optional[Product]:
    return db.query(Product).filter(Product.sku == sku, Product.tenant_id == tenant_id).first()

def get_products_by_tenant(
    db: Session,
    tenant_id: int,
    skip: int = 0,
    limit: int = 100,
    updated_since: Optional[datetime.datetime] = None
) -> List[Product]:
    query = db.query(Product).filter(Product.tenant_id == tenant_id)
    if updated_since:
        query = query.filter(Product.updated_at >= updated_since) # type: ignore
    return query.offset(skip).limit(limit).all()

def create_product(db: Session, product_in: ProductCreate, tenant_id: int) -> Product:
    existing_product_sku = get_product_by_sku_and_tenant(db, sku=product_in.sku, tenant_id=tenant_id)
    if existing_product_sku:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product with SKU '{product_in.sku}' already exists for this tenant.")

    db_product = Product(
        **product_in.dict(),
        tenant_id=tenant_id,
        version=1, # Initial version
        # last_synced_at and updated_at will default to now() via server_default/onupdate in model
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def update_product(db: Session, db_product: Product, product_in: ProductUpdate) -> Product:
    update_data = product_in.dict(exclude_unset=True)

    # Optimistic locking
    if product_in.version is not None: # Version check is only done if client provides it
        if db_product.version != product_in.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Product has been modified by another transaction. Please refresh and try again.",
            )
        db_product.version += 1 # type: ignore

    # Update fields
    for field, value in update_data.items():
        if field != 'version': # Version is handled above
            setattr(db_product, field, value)

    # Ensure SKU uniqueness if SKU is being changed
    if 'sku' in update_data and update_data['sku'] != db_product.sku: # If SKU actually changed
         existing_product_sku = get_product_by_sku_and_tenant(db, sku=update_data['sku'], tenant_id=db_product.tenant_id) # type: ignore
         if existing_product_sku and existing_product_sku.id != db_product.id : # Check it's not the same product
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product with SKU '{update_data['sku']}' already exists for this tenant.")

    # db_product.updated_at = func.now() # Handled by onupdate=func.now() in the model
    # db_product.last_synced_at = func.now() # Also handled by onupdate=func.now() in the model
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def delete_product(db: Session, db_product: Product) -> Product:
    # Consider soft delete: db_product.is_deleted = True
    # For now, hard delete:
    db.delete(db_product)
    db.commit()
    # After deletion, the db_product object is no longer valid for most operations if session is expired/closed.
    # So, it's common to return a confirmation or the object as it was before deletion (if needed).
    return db_product # Or return None, or a success message like {"detail": "Product deleted"}
