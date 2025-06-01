from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime # Import datetime for type hints if needed, though not directly used here.

from app.db.session import get_db
from app.models.sql_models import User # For current_user type hint
from app.schemas.notification_schemas import NotificationResponse, NotificationUpdate, NotificationStatusEnum
from app.services import notification_service
from app.api import deps # For RBAC (get_current_user)

router = APIRouter()

@router.get("/", response_model=List[NotificationResponse])
def list_my_notifications(
    status_filter: Optional[NotificationStatusEnum] = Query(None, alias="status"), # Use Pydantic enum from schemas
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Retrieve notifications for the currently authenticated user.
    """
    notifications = notification_service.get_notifications_for_user(
        db, user_id=current_user.id, skip=skip, limit=limit, status_filter=status_filter # type: ignore
    )
    # Pydantic's orm_mode in NotificationResponse should handle enum conversion for response.
    return notifications

@router.patch("/{notification_id}", response_model=NotificationResponse)
def update_my_notification_status(
    notification_id: int,
    notification_in: NotificationUpdate, # Uses Pydantic enum for status
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Update the status of a specific notification for the current user (e.g., mark as READ or ARCHIVED).
    """
    db_notification = notification_service.get_notification_by_id(
        db, notification_id=notification_id, user_id=current_user.id # type: ignore
    )
    if not db_notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found or access denied.")

    updated_notification = notification_service.update_notification_status(
        db=db, db_notification=db_notification, notification_update=notification_in
    )
    # Pydantic's orm_mode in NotificationResponse should handle enum conversion for response.
    return updated_notification
