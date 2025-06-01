from pydantic import BaseModel
from typing import List, Optional
import datetime
from app.schemas.order_schemas import OrderResponse, OrderItemResponse, OrderStatusEnum # For base and item details

# Tailored response for picker order list
class PickerOrderSummaryResponse(BaseModel):
    id: int
    status: OrderStatusEnum # Uses Pydantic enum from order_schemas
    pickup_slot_id: Optional[int] = None
    # Potentially add customer name hint or order urgency flags if needed by pickers
    item_count: int # Calculated field
    created_at: datetime.datetime # Order confirmation time
    updated_at: datetime.datetime # Last status update

    class Config:
        orm_mode = True

# Detailed view for a specific order for picker
class PickerOrderDetailsResponse(OrderResponse): # Inherit from full OrderResponse
    # Add any picker-specific fields if necessary, e.g., product locations
    # For now, OrderResponse might be sufficient if it includes items with product details.
    pass

class PickerReadyForPickupRequest(BaseModel):
    notes: Optional[str] = None # Optional notes from picker to counter staff
