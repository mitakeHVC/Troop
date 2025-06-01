from pydantic import BaseModel, Field
from typing import List, Optional
import datetime
import enum # For LaneStatusEnum if defined here, or import from lane_schemas

from app.schemas.order_schemas import OrderResponse, OrderStatusEnum
from app.schemas.product_schemas import ProductResponse
# from app.schemas.lane_schemas import LaneStatusEnum # Not needed if defined here or not used directly

# Tailored response for counter order list
class CounterOrderSummaryResponse(OrderResponse): # Inherits from OrderResponse
    # Can add specific fields for counter if needed, e.g., customer arrival status
    pass

# Schema for data returned to counter staff after QR scan for verification
class OrderVerificationDataResponse(BaseModel):
    order_id: int
    pickup_token: str
    customer_username: Optional[str] = None
    status: OrderStatusEnum # Current status of the order

    # Details for asking verification questions:
    identity_verification_product_name: Optional[str] = None
    identity_verification_product_description: Optional[str] = None # e.g., SKU, variant

    other_item_hints: List[str] = [] # e.g., list of product names or categories in the order

class CounterAssignOrderToLaneRequest(BaseModel):
    lane_id: int
    # order_id is from path

class CounterOrderCompleteRequest(BaseModel): # For the /orders/{order_id}/complete-pickup endpoint
    notes: Optional[str] = None # Optional notes from counter staff
