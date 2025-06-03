"""
Service layer for managing pickup time slots.

This module provides functions for creating, retrieving, updating,
deleting, and managing capacity for pickup time slots.
"""
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime
from app.models.sql_models import PickupTimeSlot
from app.models.sql_models import LaneStatus as DBLaneStatusEnum # Not used here, but good practice if related
from app.schemas.timeslot_schemas import PickupTimeSlotCreate, PickupTimeSlotUpdate
from app.schemas.notification_schemas import NotificationStatusEnum # Corrected import
# For timeslot, is_active is a boolean. If filtering by a status enum, it would be defined in timeslot_schemas.
# The current filter `is_active: Optional[bool]` is fine.
from fastapi import HTTPException, status

def get_timeslot_by_id(db: Session, timeslot_id: int, tenant_id: int) -> Optional[PickupTimeSlot]:
    """
    Retrieves a specific pickup time slot by its ID and tenant ID.

    Args:
        db: SQLAlchemy database session.
        timeslot_id: ID of the timeslot to retrieve.
        tenant_id: ID of the tenant to which the timeslot belongs.

    Returns:
        The PickupTimeSlot object if found, else None.
    """
    return db.query(PickupTimeSlot).filter(PickupTimeSlot.id == timeslot_id, PickupTimeSlot.tenant_id == tenant_id).first()

def get_timeslots_by_tenant(
    db: Session,
    tenant_id: int,
    skip: int = 0,
    limit: int = 100,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
    only_available: bool = False,
    is_active: Optional[bool] = True
) -> List[PickupTimeSlot]:
    """
    Retrieves a list of pickup time slots for a given tenant, with various filtering options.

    Args:
        db: SQLAlchemy database session.
        tenant_id: ID of the tenant.
        skip: Number of records to skip (for pagination).
        limit: Maximum number of records to return (for pagination).
        date_from: Filter slots from this date onwards.
        date_to: Filter slots up to this date.
        only_available: If True, only return slots with capacity > current_orders.
        is_active: Filter by active status (True, False, or None for all).

    Returns:
        A list of PickupTimeSlot objects.
    """
    query = db.query(PickupTimeSlot).filter(PickupTimeSlot.tenant_id == tenant_id)

    if date_from:
        query = query.filter(PickupTimeSlot.date >= date_from)
    if date_to:
        query = query.filter(PickupTimeSlot.date <= date_to)
    if only_available:
        query = query.filter(PickupTimeSlot.capacity > PickupTimeSlot.current_orders)
    if is_active is not None: # Allows filtering for False or True
        query = query.filter(PickupTimeSlot.is_active == is_active)

    return query.order_by(PickupTimeSlot.date, PickupTimeSlot.start_time).offset(skip).limit(limit).all()

def create_timeslot(db: Session, timeslot_create_data: PickupTimeSlotCreate, tenant_id: int) -> PickupTimeSlot:
    """
    Creates a new pickup time slot for a tenant.

    Args:
        db: SQLAlchemy database session.
        timeslot_create_data: Pydantic schema with timeslot creation data.
        tenant_id: ID of the tenant.

    Raises:
        HTTPException (400): If validation fails (e.g., end time before start, non-positive capacity).

    Returns:
        The newly created PickupTimeSlot object.
    """
    if timeslot_create_data.end_time <= timeslot_create_data.start_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End time must be after start time.")
    if timeslot_create_data.capacity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Capacity must be positive.")

    # TODO: Consider adding validation for overlapping time slots for the same tenant.

    db_timeslot = PickupTimeSlot(
        **timeslot_create_data.model_dump(),
        tenant_id=tenant_id,
        current_orders=0
    )
    db.add(db_timeslot)
    db.commit()
    db.refresh(db_timeslot)
    return db_timeslot

def update_timeslot(db: Session, db_timeslot: PickupTimeSlot, timeslot_update_data: PickupTimeSlotUpdate) -> PickupTimeSlot:
    """
    Updates an existing pickup time slot.

    Args:
        db: SQLAlchemy database session.
        db_timeslot: The existing PickupTimeSlot ORM instance to update.
        timeslot_update_data: Pydantic schema with update data.

    Raises:
        HTTPException (400): If validation fails (e.g., capacity constraints, invalid times).

    Returns:
        The updated PickupTimeSlot object.
    """
    update_data = timeslot_update_data.model_dump(exclude_unset=True)

    current_start_time = db_timeslot.start_time
    current_end_time = db_timeslot.end_time

    new_start_time = update_data.get("start_time", current_start_time)
    new_end_time = update_data.get("end_time", current_end_time)

    if new_end_time <= new_start_time: # type: ignore
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End time must be after start time.")

    if "capacity" in update_data:
        new_capacity = update_data["capacity"]
        if new_capacity is not None and new_capacity <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Capacity must be positive.")
        if new_capacity is not None and new_capacity < db_timeslot.current_orders: # type: ignore
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"New capacity ({new_capacity}) cannot be less than current booked orders ({db_timeslot.current_orders}).")

    for field, value in update_data.items():
        setattr(db_timeslot, field, value)

    db.add(db_timeslot)
    db.commit()
    db.refresh(db_timeslot)
    return db_timeslot

def delete_timeslot(db: Session, db_timeslot: PickupTimeSlot) -> PickupTimeSlot:
    """
    Deletes a pickup time slot. Prevents deletion if there are current booked orders.

    Args:
        db: SQLAlchemy database session.
        db_timeslot: The PickupTimeSlot ORM instance to delete.

    Raises:
        HTTPException (400): If timeslot has booked orders.

    Returns:
        The deleted PickupTimeSlot object (transient after commit).
    """
    if db_timeslot.current_orders > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot delete time slot with {db_timeslot.current_orders} booked orders. Consider deactivating it instead.")

    db.delete(db_timeslot)
    db.commit()
    return db_timeslot

def increment_slot_order_count(db: Session, timeslot_id: int, tenant_id: int) -> Optional[PickupTimeSlot]:
    """
    Increments the current_orders count for a timeslot.
    Does NOT commit the session; relies on the calling function to commit.

    Args:
        db: SQLAlchemy database session.
        timeslot_id: ID of the timeslot.
        tenant_id: ID of the tenant owning the timeslot.

    Returns:
        The updated PickupTimeSlot object if found and incremented, else None.
    Raises:
        HTTPException (400/409): If slot is inactive or full.
    """
    slot = get_timeslot_by_id(db, timeslot_id, tenant_id)
    if slot:
        if not slot.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot book order for an inactive time slot.")
        if slot.current_orders < slot.capacity: # type: ignore
            slot.current_orders += 1 # type: ignore
            db.add(slot)
            db.flush() # Make change available in current transaction
            db.refresh(slot)
            return slot
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Time slot is full.")
    return None # Or raise HTTPException(status_code=404, detail="Timeslot not found")

def decrement_slot_order_count(db: Session, timeslot_id: int, tenant_id: int) -> Optional[PickupTimeSlot]:
    """
    Decrements the current_orders count for a timeslot.
    Does NOT commit the session; relies on the calling function to commit.

    Args:
        db: SQLAlchemy database session.
        timeslot_id: ID of the timeslot.
        tenant_id: ID of the tenant owning the timeslot.

    Returns:
        The updated PickupTimeSlot object if found and decremented, else None.
    """
    slot = get_timeslot_by_id(db, timeslot_id, tenant_id)
    if slot:
        if slot.current_orders > 0: # type: ignore
            slot.current_orders -= 1 # type: ignore
            db.add(slot)
            db.flush() # Make change available in current transaction
            db.refresh(slot)
            return slot
        # else: current_orders is already 0, no change needed or raise error if desired.
    return None # Or raise HTTPException(status_code=404, detail="Timeslot not found")
