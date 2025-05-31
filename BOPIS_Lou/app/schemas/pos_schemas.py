from pydantic import BaseModel, Field
from typing import List, Optional
import decimal

class POSOrderItemSchema(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0) # Quantity must be positive

class POSOrderCreateRequest(BaseModel):
    items: List[POSOrderItemSchema]
    # Mock payment details for now
    payment_method: str = "cash" # e.g., "cash", "card_mock"
    # tenant_id is derived from authenticated staff user
    # staff_id (user_id of staff processing sale) is also from authenticated user
    idempotency_key: Optional[str] = None # For client-side idempotency
