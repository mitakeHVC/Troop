from pydantic import BaseModel
from typing import Optional, List
import datetime
import decimal # For Numeric/Decimal type from SQLAlchemy

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: decimal.Decimal
    sku: str
    stock_quantity: int = 0
    image_url: Optional[str] = None

class ProductCreate(ProductBase):
    pass # tenant_id will be derived from the authenticated user

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[decimal.Decimal] = None
    sku: Optional[str] = None # SKU might be updatable by admin, ensure uniqueness per tenant
    stock_quantity: Optional[int] = None
    image_url: Optional[str] = None
    version: Optional[int] = None # Required for optimistic lock check when updating critical fields

class ProductResponse(ProductBase):
    id: int
    tenant_id: int
    version: int
    last_synced_at: datetime.datetime # Included as per self-correction in prompt
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True
