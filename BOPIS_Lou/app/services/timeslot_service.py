from sqlalchemy.orm import Session
from typing import List, Optional
import datetime
from app.models.sql_models import PickupTimeSlot
from app.schemas.timeslot_schemas import PickupTimeSlotCreate, PickupTimeSlotUpdate
from fastapi import HTTPException, status # Added status for HTTPException

def get_timeslot_by_id(db: Session, timeslot_id: int, tenant_id: int) -> Optional[PickupTimeSlot]:
    return db.query(PickupTimeSlot).filter(PickupTimeSlot.id == timeslot_id, PickupTimeSlot.tenant_id == tenant_id).first()

def get_timeslots_by_tenant(
    db: Session,
    tenant_id: int,
    skip: int = 0,
    limit: int = 100,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
    only_available: bool = False, # If true, only slots with capacity > current_orders
    is_active: Optional[bool] = True # Filter by active status
) -> List[PickupTimeSlot]:
    query = db.query(PickupTimeSlot).filter(PickupTimeSlot.tenant_id == tenant_id)

    if date_from:
        query = query.filter(PickupTimeSlot.date >= date_from) # type: ignore
    if date_to:
        query = query.filter(PickupTimeSlot.date <= date_to) # type: ignore
    if only_available:
        query = query.filter(PickupTimeSlot.capacity > PickupTimeSlot.current_orders) # type: ignore
    if is_active is not None:
        query = query.filter(PickupTimeSlot.is_active == is_active) # type: ignore

    return query.order_by(PickupTimeSlot.date, PickupTimeSlot.start_time).offset(skip).limit(limit).all() # type: ignore

def create_timeslot(db: Session, timeslot_in: PickupTimeSlotCreate, tenant_id: int) -> PickupTimeSlot:
    # Add validation: end_time > start_time, capacity > 0
    if timeslot_in.end_time <= timeslot_in.start_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End time must be after start time.")
    if timeslot_in.capacity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Capacity must be positive.")

    # Check for overlapping slots for the same tenant (more complex validation, optional for now)
    # This would involve querying existing slots for the tenant on the same date and checking time ranges.

    db_timeslot = PickupTimeSlot(
        **timeslot_in.dict(),
        tenant_id=tenant_id,
        current_orders=0 # Initialize current_orders
    )
    db.add(db_timeslot)
    db.commit()
    db.refresh(db_timeslot)
    return db_timeslot

def update_timeslot(db: Session, db_timeslot: PickupTimeSlot, timeslot_in: PickupTimeSlotUpdate) -> PickupTimeSlot:
    update_data = timeslot_in.dict(exclude_unset=True)

    # Validate start/end times if both are provided or one is changing relative to existing
    # This logic needs to access db_timeslot's existing values if only one is in update_data
    current_start_time = db_timeslot.start_time
    current_end_time = db_timeslot.end_time

    new_start_time = update_data.get("start_time", current_start_time)
    new_end_time = update_data.get("end_time", current_end_time)

    if new_end_time <= new_start_time: # type: ignore
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End time must be after start time.")

    if "capacity" in update_data:
        new_capacity = update_data["capacity"]
        if new_capacity is not None and new_capacity <= 0: # type: ignore
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
    if db_timeslot.current_orders > 0:
        # Or, alternatively, allow deletion but then orders need to be handled (e.g., re-assign slot, notify customer)
        # For now, prevent deletion if orders are booked.
        # Another option is to just mark is_active=False
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot delete time slot with {db_timeslot.current_orders} booked orders. Consider deactivating it instead.")

    db.delete(db_timeslot)
    db.commit()
    return db_timeslot # Or return None or a success message

# Function to increment/decrement current_orders (called by order service)
def increment_slot_order_count(db: Session, timeslot_id: int, tenant_id: int) -> Optional[PickupTimeSlot]:
    slot = get_timeslot_by_id(db, timeslot_id, tenant_id)
    if slot:
        if not slot.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot book order for an inactive time slot.")
        if slot.current_orders < slot.capacity:
            slot.current_orders += 1 # type: ignore
            db.commit()
            db.refresh(slot)
            return slot
        else:
            # This case should ideally be caught before calling increment
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Time slot is full.")
    return None # Or raise not found

def decrement_slot_order_count(db: Session, timeslot_id: int, tenant_id: int) -> Optional[PickupTimeSlot]:
    slot = get_timeslot_by_id(db, timeslot_id, tenant_id)
    if slot:
        if slot.current_orders > 0:
            slot.current_orders -= 1 # type: ignore
            db.commit()
            db.refresh(slot)
            return slot
        # else:
            # Optionally log or raise if trying to decrement below zero, though current_orders should be >= 0
    return None # Or raise not found
