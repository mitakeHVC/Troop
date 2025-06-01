"""
Service layer for managing user notifications.

This module provides functions for retrieving and updating notifications
for users. Notification creation is typically handled by other services
based on business events.
"""
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime
from app.models.sql_models import Notification
from app.models.sql_models import NotificationStatus as DBNotificationStatusEnum
from app.schemas.notification_schemas import NotificationUpdate, NotificationStatusEnum as PydanticNotificationStatusEnum
# from fastapi import HTTPException, status # status not currently used

def get_notifications_for_user(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[PydanticNotificationStatusEnum] = None
) -> List[Notification]:
    """
    Retrieves a list of notifications for a specific user, with optional filtering by status.

    Args:
        db: SQLAlchemy database session.
        user_id: ID of the user whose notifications are to be retrieved.
        skip: Number of records to skip (for pagination).
        limit: Maximum number of records to return (for pagination).
        status_filter: Pydantic enum to filter notifications by their status.

    Returns:
        A list of Notification objects.
    """
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if status_filter:
        query = query.filter(Notification.status == DBNotificationStatusEnum[status_filter.value])

    return query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()

def get_notification_by_id(db: Session, notification_id: int, user_id: int) -> Optional[Notification]:
    """
    Retrieves a specific notification by its ID, ensuring it belongs to the specified user.

    Args:
        db: SQLAlchemy database session.
        notification_id: ID of the notification to retrieve.
        user_id: ID of the user who should own the notification.

    Returns:
        The Notification object if found and owned by the user, else None.
    """
    return db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user_id).first()

def update_notification_status(
    db: Session,
    db_notification: Notification,
    notification_update_data: NotificationUpdate # Renamed for clarity
) -> Notification:
    """
    Updates the status of a notification (e.g., to READ or ARCHIVED).
    Sets the `read_at` timestamp if status is changed to READ and `read_at` is not already set.

    Args:
        db: SQLAlchemy database session.
        db_notification: The existing Notification ORM instance to update.
        notification_update_data: Pydantic schema containing the new status.

    Returns:
        The updated Notification object.
    """
    db_notification.status = DBNotificationStatusEnum[notification_update_data.status.value] # type: ignore

    if notification_update_data.status == PydanticNotificationStatusEnum.READ and not db_notification.read_at:
        db_notification.read_at = datetime.datetime.utcnow()

    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification

# TODO: Refactor notification creation logic from other services (like order_service)
# into a centralized `create_notification` function here. Example:
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
