import pytest
from sqlalchemy.orm import Session as SQLAlchemySession
from fastapi import HTTPException
from app.services import timeslot_service
from app.schemas.timeslot_schemas import PickupTimeSlotCreate, PickupTimeSlotUpdate
from app.models.sql_models import Tenant, PickupTimeSlot
import datetime

@pytest.fixture
def test_tenant_for_slots(db_session: SQLAlchemySession) -> Tenant:
    tenant = Tenant(name="TimeslotServiceTestTenant") # Unique name for this test module
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant

def test_create_timeslot(db_session: SQLAlchemySession, test_tenant_for_slots: Tenant):
    slot_data = PickupTimeSlotCreate(
        date=datetime.date.today() + datetime.timedelta(days=1),
        start_time=datetime.time(10,0),
        end_time=datetime.time(11,0),
        capacity=10,
        is_active=True
    )
    slot = timeslot_service.create_timeslot(db_session, timeslot_in=slot_data, tenant_id=test_tenant_for_slots.id)
    assert slot is not None
    assert slot.date == slot_data.date
    assert slot.capacity == 10
    assert slot.current_orders == 0

def test_create_timeslot_validations(db_session: SQLAlchemySession, test_tenant_for_slots: Tenant):
    # Invalid time (end <= start)
    slot_data_invalid_time = PickupTimeSlotCreate(
        date=datetime.date.today(),
        start_time=datetime.time(10,0),
        end_time=datetime.time(9,0),
        capacity=5
    )
    with pytest.raises(HTTPException) as excinfo:
        timeslot_service.create_timeslot(db_session, timeslot_in=slot_data_invalid_time, tenant_id=test_tenant_for_slots.id)
    assert excinfo.value.status_code == 400
    assert "End time must be after start time" in excinfo.value.detail

    # Invalid capacity (<=0)
    slot_data_invalid_capacity = PickupTimeSlotCreate(
        date=datetime.date.today(),
        start_time=datetime.time(10,0),
        end_time=datetime.time(11,0),
        capacity=0
    )
    with pytest.raises(HTTPException) as excinfo:
        timeslot_service.create_timeslot(db_session, timeslot_in=slot_data_invalid_capacity, tenant_id=test_tenant_for_slots.id)
    assert excinfo.value.status_code == 400
    assert "Capacity must be positive" in excinfo.value.detail

def test_update_timeslot_capacity_validation(db_session: SQLAlchemySession, test_tenant_for_slots: Tenant):
    slot_data = PickupTimeSlotCreate(
        date=datetime.date.today(),
        start_time=datetime.time(14,0),
        end_time=datetime.time(15,0),
        capacity=2
    )
    db_slot = timeslot_service.create_timeslot(db_session, timeslot_in=slot_data, tenant_id=test_tenant_for_slots.id)

    db_slot.current_orders = 2 # Simulate booked orders to capacity
    db_session.commit()
    db_session.refresh(db_slot)

    # Try to update capacity to less than current_orders
    update_data_less_than_booked = PickupTimeSlotUpdate(capacity=1)
    with pytest.raises(HTTPException) as excinfo_booked:
        timeslot_service.update_timeslot(db_session, db_slot=db_slot, timeslot_in=update_data_less_than_booked)
    assert excinfo_booked.value.status_code == 400
    assert "cannot be less than current booked orders" in excinfo_booked.value.detail

    # Try to update capacity to be zero or negative when orders are booked (even if it's not less than current)
    update_data_invalid_cap = PickupTimeSlotUpdate(capacity=0)
    with pytest.raises(HTTPException) as excinfo_invalid_cap:
        timeslot_service.update_timeslot(db_session, db_slot=db_slot, timeslot_in=update_data_invalid_cap)
    assert excinfo_invalid_cap.value.status_code == 400
    assert "Capacity must be positive" in excinfo_invalid_cap.value.detail


def test_delete_timeslot_with_booked_orders(db_session: SQLAlchemySession, test_tenant_for_slots: Tenant):
    slot_data = PickupTimeSlotCreate(
        date=datetime.date.today(),
        start_time=datetime.time(16,0),
        end_time=datetime.time(17,0),
        capacity=1
    )
    db_slot = timeslot_service.create_timeslot(db_session, timeslot_in=slot_data, tenant_id=test_tenant_for_slots.id)

    db_slot.current_orders = 1 # Simulate booked order
    db_session.commit()
    db_session.refresh(db_slot)

    with pytest.raises(HTTPException) as excinfo:
        timeslot_service.delete_timeslot(db_session, db_slot=db_slot)
    assert excinfo.value.status_code == 400
    assert f"Cannot delete time slot with {db_slot.current_orders} booked orders" in excinfo.value.detail # type: ignore

def test_increment_decrement_slot_order_count(db_session: SQLAlchemySession, test_tenant_for_slots: Tenant):
    slot_data = PickupTimeSlotCreate(
        date=datetime.date.today(),
        start_time=datetime.time(18,0),
        end_time=datetime.time(19,0),
        capacity=1 # Capacity of 1
    )
    db_slot = timeslot_service.create_timeslot(db_session, timeslot_in=slot_data, tenant_id=test_tenant_for_slots.id)
    assert db_slot.current_orders == 0

    # Increment once
    updated_slot = timeslot_service.increment_slot_order_count(db_session, timeslot_id=db_slot.id, tenant_id=test_tenant_for_slots.id)
    assert updated_slot is not None
    assert updated_slot.current_orders == 1

    # Try to increment again (slot is full)
    with pytest.raises(HTTPException) as excinfo_full:
        timeslot_service.increment_slot_order_count(db_session, timeslot_id=db_slot.id, tenant_id=test_tenant_for_slots.id)
    assert excinfo_full.value.status_code == 409
    assert "Time slot is full" in excinfo_full.value.detail

    # Decrement once
    updated_slot_decremented = timeslot_service.decrement_slot_order_count(db_session, timeslot_id=db_slot.id, tenant_id=test_tenant_for_slots.id)
    assert updated_slot_decremented is not None
    assert updated_slot_decremented.current_orders == 0

    # Try to decrement again (already 0)
    # The service function currently returns None if current_orders is 0, no exception.
    # This behavior can be tested.
    updated_slot_already_zero = timeslot_service.decrement_slot_order_count(db_session, timeslot_id=db_slot.id, tenant_id=test_tenant_for_slots.id)
    assert updated_slot_already_zero is not None # It will return the slot with current_orders = 0
    assert updated_slot_already_zero.current_orders == 0 # Still 0

    # Test increment on inactive slot
    db_slot.is_active = False
    db_session.commit()
    db_session.refresh(db_slot)
    with pytest.raises(HTTPException) as excinfo_inactive:
        timeslot_service.increment_slot_order_count(db_session, timeslot_id=db_slot.id, tenant_id=test_tenant_for_slots.id)
    assert excinfo_inactive.value.status_code == 400
    assert "Cannot book order for an inactive time slot" in excinfo_inactive.value.detail
