from pydantic import BaseModel, Field
from typing import List, Optional
import datetime
import decimal # For Numeric/Decimal type
import enum # Required for Pydantic enums

from app.schemas.user_schemas import UserResponse
from app.schemas.product_schemas import ProductResponse
from app.schemas.timeslot_schemas import PickupTimeSlotResponse
from app.schemas.lane_schemas import LaneResponse
# Enums will be defined here for Pydantic validation, separate from DB enums
# from app.models.sql_models import OrderType as DBOrderTypeEnum, OrderStatus as DBOrderStatusEnum, PaymentStatus as DBPaymentStatusEnum

class OrderTypeEnum(str, enum.Enum):
    BOPIS = "BOPIS"
    POS_SALE = "POS_SALE"

class OrderStatusEnum(str, enum.Enum):
    CART = "CART"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    PROCESSING = "PROCESSING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"

class PaymentStatusEnum(str, enum.Enum):
    UNPAID = "UNPAID"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

# OrderItem Schemas
class OrderItemBase(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0) # Quantity must be positive

class OrderItemCreate(OrderItemBase):
    # price_at_purchase will be set by service based on current product price
    pass

class OrderItemUpdate(BaseModel): # Used for updating quantity in cart
    quantity: int = Field(..., gt=0)

class OrderItemResponse(OrderItemBase):
    id: int
    order_id: int
    price_at_purchase: decimal.Decimal
    product: Optional[ProductResponse] = None # Optionally populated

    class Config:
        orm_mode = True

# Order Schemas
class OrderBase(BaseModel):
    # user_id and tenant_id are typically set by the system based on context
    order_type: OrderTypeEnum = OrderTypeEnum.BOPIS # Default for cart/online orders
    # status and payment_status have defaults or set by system logic
    pass

class OrderCreate(OrderBase): # Used internally by service when a cart is first created
    user_id: int
    tenant_id: int # Tenant context for the order

class OrderResponse(OrderBase):
    id: int
    user_id: int
    tenant_id: int
    status: OrderStatusEnum
    payment_status: PaymentStatusEnum
    total_amount: decimal.Decimal
    pickup_token: Optional[str] = None
    pickup_slot_id: Optional[int] = None
    assigned_lane_id: Optional[int] = None
    identity_verification_product_id: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    customer: Optional[UserResponse] = None
    order_items: List[OrderItemResponse] = []
    pickup_slot: Optional[PickupTimeSlotResponse] = None
    assigned_lane: Optional[LaneResponse] = None

    class Config:
        orm_mode = True

# Cart specific schemas (request bodies for API endpoints)
class CartItemCreateRequest(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)
    # tenant_id is not in the request body for adding to cart;
    # it's established when the cart is created or from the user's context.

class CartItemUpdateRequest(BaseModel): # For /cart/items/{item_id} PUT
    quantity: int = Field(..., gt=0)

class CheckoutRequestSchema(BaseModel):
    pickup_slot_id: int
    # identity_verification_product_id: Optional[int] = None # System can pick this based on order items.
    # payment_details: Optional[dict] # For future actual payment integration
    idempotency_key: Optional[str] = None # For client-side idempotency of checkout

class OrderPickupTokenVerificationRequest(BaseModel): # Added this schema
    pickup_token: str
