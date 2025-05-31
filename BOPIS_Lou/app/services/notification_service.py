from sqlalchemy.orm import Session
from typing import List, Optional
import datetime
from app.models.sql_models import Notification, User # User might not be needed directly here but good for context
from app.models.sql_models import NotificationStatus as DBNotificationStatusEnum # Import DB enum
from app.schemas.notification_schemas import NotificationUpdate, NotificationStatusEnum as PydanticNotificationStatusEnum
from fastapi import HTTPException, status

def get_notifications_for_user(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[PydanticNotificationStatusEnum] = None
) -> List[Notification]:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if status_filter:
        # Convert Pydantic enum to DB enum for query
        query = query.filter(Notification.status == DBNotificationStatusEnum[status_filter.value])

    return query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all() # type: ignore

def get_notification_by_id(db: Session, notification_id: int, user_id: int) -> Optional[Notification]:
    # Ensure user owns the notification
    return db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user_id).first()

def update_notification_status(
    db: Session,
    db_notification: Notification,
    notification_update: NotificationUpdate
) -> Notification:
    # Convert Pydantic enum to DB enum before assigning
    db_notification.status = DBNotificationStatusEnum[notification_update.status.value] # type: ignore

    if notification_update.status == PydanticNotificationStatusEnum.READ and not db_notification.read_at:
        db_notification.read_at = datetime.datetime.utcnow()
    # Add logic for ARCHIVED if it means something different (e.g., soft delete or different view)
    # For now, ARCHIVED is just another status.

    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification

# The notification creation logic is currently in order_service.py.
# It could be moved here for centralization if preferred in a future refactor:
# def create_notification(db: Session, user_id: int, tenant_id: int, message: str, related_order_id: Optional[int] = None) -> Notification:
#     db_notification = Notification(
#         user_id=user_id,
#         tenant_id=tenant_id,
#         message=message,
#         related_order_id=related_order_id
#         # status defaults to UNREAD via model definition
#     )
#     db.add(db_notification)
#     db.commit()
#     db.refresh(db_notification)
#     return db_notification
