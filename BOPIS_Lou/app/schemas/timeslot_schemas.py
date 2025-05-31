from pydantic import BaseModel
from typing import Optional, List
import datetime

class PickupTimeSlotBase(BaseModel):
    date: datetime.date # Store as date, API receives date
    start_time: datetime.time
    end_time: datetime.time
    capacity: int
    is_active: bool = True

class PickupTimeSlotCreate(PickupTimeSlotBase):
    pass # tenant_id will be derived from the authenticated user or path

class PickupTimeSlotResponse(PickupTimeSlotBase):
    id: int
    tenant_id: int
    current_orders: int # Number of orders currently booked for this slot
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True

class PickupTimeSlotUpdate(BaseModel):
    date: Optional[datetime.date] = None
    start_time: Optional[datetime.time] = None
    end_time: Optional[datetime.time] = None
    capacity: Optional[int] = None
    is_active: Optional[bool] = None
    # current_orders is typically managed by the system when orders are placed/cancelled
