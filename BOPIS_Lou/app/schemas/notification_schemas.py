from pydantic import BaseModel
from typing import Optional, List
import datetime
import enum # Required for Pydantic enum definition

# Import enum from models for use in Pydantic schemas
# from app.models.sql_models import NotificationStatus as DBNotificationStatusEnum # Not directly used, define Pydantic version

class NotificationStatusEnum(str, enum.Enum): # Pydantic version
    UNREAD = "UNREAD"
    READ = "READ"
    ARCHIVED = "ARCHIVED"

class NotificationResponse(BaseModel):
    id: int
    user_id: int # The user this notification is for
    tenant_id: int # Tenant context of the notification
    message: str
    related_order_id: Optional[int] = None
    status: NotificationStatusEnum # Use Pydantic enum
    created_at: datetime.datetime
    read_at: Optional[datetime.datetime] = None
    # Optionally include related Order or User details if needed in response
    # related_order: Optional[OrderResponse] = None
    # user: Optional[UserResponse] = None

    class Config:
        orm_mode = True

class NotificationUpdate(BaseModel):
    status: NotificationStatusEnum # e.g., mark as READ or ARCHIVED
