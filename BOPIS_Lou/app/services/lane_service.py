"""
Service layer for lane management and staff assignments to lanes.

This module handles the business logic for creating, retrieving, updating,
deleting lanes, managing their status, and assigning/unassigning staff.
"""
from sqlalchemy.orm import Session, selectinload # Added selectinload
from typing import List, Optional
from app.models.sql_models import Lane, StaffAssignment, User, Order
from app.models.sql_models import UserRole as DBUserRole
from app.models.sql_models import LaneStatus as DBLaneStatus
from app.schemas.lane_schemas import LaneCreate, LaneUpdate
from app.schemas.lane_schemas import LaneStatusEnum as PydanticLaneStatusEnum
from fastapi import HTTPException, status

def get_lane_by_id(db: Session, lane_id: int, tenant_id: int) -> Optional[Lane]:
    """
    Retrieves a lane by its ID and tenant ID.

    Args:
        db: SQLAlchemy database session.
        lane_id: ID of the lane to retrieve.
        tenant_id: ID of the tenant to which the lane belongs.

    Returns:
        The Lane object if found, else None.
    """
    return db.query(Lane).filter(Lane.id == lane_id, Lane.tenant_id == tenant_id).first()

def get_lanes_by_tenant(
    db: Session,
    tenant_id: int,
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[PydanticLaneStatusEnum] = None
) -> List[Lane]:
    """
    Retrieves a list of lanes for a given tenant, with optional status filtering and pagination.

    Args:
        db: SQLAlchemy database session.
        tenant_id: ID of the tenant.
        skip: Number of records to skip.
        limit: Maximum number of records to return.
        status_filter: Pydantic enum to filter lanes by their status.

    Returns:
        A list of Lane objects.
    """
    query = db.query(Lane).filter(Lane.tenant_id == tenant_id)
    if status_filter:
        query = query.filter(Lane.status == DBLaneStatus[status_filter.value])
    return query.order_by(Lane.name).offset(skip).limit(limit).all()

def create_lane(db: Session, lane_create_data: LaneCreate, tenant_id: int) -> Lane:
    """
    Creates a new lane for a tenant.

    Args:
        db: SQLAlchemy database session.
        lane_create_data: Pydantic schema with lane creation data.
        tenant_id: ID of the tenant.

    Returns:
        The newly created Lane object.
    """
    db_lane = Lane(
        name=lane_create_data.name,
        status=DBLaneStatus[lane_create_data.status.value],
        tenant_id=tenant_id
    )
    db.add(db_lane)
    db.commit()
    db.refresh(db_lane)
    return db_lane

def update_lane_details(db: Session, db_lane: Lane, lane_update_data: LaneUpdate) -> Lane:
    """
    Updates details of an existing lane (e.g., name, status).

    Args:
        db: SQLAlchemy database session.
        db_lane: The existing Lane ORM instance to update.
        lane_update_data: Pydantic schema with lane update data.

    Returns:
        The updated Lane object.
    """
    update_data = lane_update_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value is not None:
            if isinstance(value, PydanticLaneStatusEnum):
                setattr(db_lane, field, DBLaneStatus[value.value])
            else: # Should ideally not happen if router uses Pydantic enum
                setattr(db_lane, field, value)
        else:
            setattr(db_lane, field, value)
    db.add(db_lane)
    db.commit()
    db.refresh(db_lane)
    return db_lane

def update_lane_status(db: Session, db_lane: Lane, new_status: PydanticLaneStatusEnum) -> Lane:
    """
    Updates the status of a specific lane. If set to OPEN, clears current_order_id.

    Args:
        db: SQLAlchemy database session.
        db_lane: The Lane ORM instance to update.
        new_status: The new status for the lane (Pydantic enum).

    Returns:
        The updated Lane object.
    """
    db_lane.status = DBLaneStatus[new_status.value]
    if new_status == PydanticLaneStatusEnum.OPEN:
        db_lane.current_order_id = None # type: ignore

    db.add(db_lane)
    db.commit()
    db.refresh(db_lane)
    return db_lane

def delete_lane(db: Session, db_lane: Lane) -> Lane:
    """
    Deletes a lane. Prevents deletion if active staff assignments or current order exist.

    Args:
        db: SQLAlchemy database session.
        db_lane: The Lane ORM instance to delete.

    Raises:
        HTTPException (400): If lane cannot be deleted due to dependencies.

    Returns:
        The deleted Lane object (transient after commit).
    """
    active_assignments = db.query(StaffAssignment).filter(
        StaffAssignment.lane_id == db_lane.id,
        StaffAssignment.is_active == True
    ).count()
    if active_assignments > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lane has active staff assignments. Please unassign staff first.")

    if db_lane.current_order_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lane is currently processing an order or has an order assigned.")

    db.delete(db_lane)
    db.commit()
    return db_lane


def assign_order_to_lane(db: Session, lane: Lane, order: Order, counter_user: User) -> Lane:
    """
    Assigns an order to a lane, setting lane status to BUSY.

    Args:
        db: SQLAlchemy database session.
        lane: The Lane to assign the order to.
        order: The Order to be assigned.
        counter_user: The counter staff performing the assignment (for tenant validation).

    Raises:
        HTTPException: If lane/order not in user's tenant, lane not OPEN, or already busy/assigned.

    Returns:
        The updated Lane object.
    """
    if lane.tenant_id != counter_user.tenant_id or order.tenant_id != counter_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage resources outside of user's tenant.")
    if lane.status != DBLaneStatus.OPEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Lane is not OPEN. Current status: {lane.status.value}") # type: ignore
    if lane.current_order_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Lane is already busy with order {lane.current_order_id}.")
    if order.assigned_lane_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order {order.id} is already assigned to lane {order.assigned_lane_id}.")

    lane.current_order_id = order.id # type: ignore
    lane.status = DBLaneStatus.BUSY # type: ignore
    order.assigned_lane_id = lane.id # type: ignore

    db.add(lane)
    db.add(order)
    db.commit()
    db.refresh(lane)
    return lane

def clear_lane_and_set_open(db: Session, lane_id: int, tenant_id: int) -> Optional[Lane]:
    """
    Clears the current order from a lane and sets its status to OPEN.

    Args:
        db: SQLAlchemy database session.
        lane_id: ID of the lane to clear.
        tenant_id: ID of the tenant owning the lane.

    Returns:
        The updated Lane object if found, else None.
    """
    lane = get_lane_by_id(db, lane_id=lane_id, tenant_id=tenant_id)
    if lane:
        lane.current_order_id = None # type: ignore
        lane.status = DBLaneStatus.OPEN # type: ignore
        db.add(lane)
        db.commit()
        db.refresh(lane)
        return lane
    return None

def assign_staff_to_lane(db: Session, lane: Lane, user_id: int, tenant_id: int) -> StaffAssignment:
    """
    Assigns a 'counter' staff member to a lane. Deactivates their previous active assignments.

    Args:
        db: SQLAlchemy database session.
        lane: The Lane to assign staff to.
        user_id: ID of the User (staff member) to assign.
        tenant_id: ID of the tenant.

    Raises:
        HTTPException: If staff not found, not a counter, or other assignment issues.

    Returns:
        The created StaffAssignment object.
    """
    staff_user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
    if not staff_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found in this tenant.")
    if staff_user.role != DBUserRole.counter:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only 'counter' staff can be assigned to lanes.")

    # Deactivate previous active assignments for this user
    existing_assignments = db.query(StaffAssignment).filter(
        StaffAssignment.user_id == user_id,
        StaffAssignment.is_active == True
    ).all()
    for assign in existing_assignments:
        assign.is_active = False
        db.add(assign)

    assignment = StaffAssignment(
        user_id=user_id,
        lane_id=lane.id,
        tenant_id=tenant_id,
        assigned_role=DBUserRole.counter,
        is_active=True
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment

def unassign_staff_from_lane(db: Session, assignment_id: int, lane_id: int, tenant_id: int) -> StaffAssignment:
    """
    Deactivates a staff assignment from a lane.

    Args:
        db: SQLAlchemy database session.
        assignment_id: ID of the StaffAssignment record.
        lane_id: ID of the lane (for verification).
        tenant_id: ID of the tenant (for verification).

    Raises:
        HTTPException: If assignment not found or already inactive.

    Returns:
        The updated (deactivated) StaffAssignment object.
    """
    assignment = db.query(StaffAssignment).filter(
        StaffAssignment.id == assignment_id,
        StaffAssignment.lane_id == lane_id,
        StaffAssignment.tenant_id == tenant_id
    ).first()

    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff assignment not found for this lane and tenant.")

    if not assignment.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Staff assignment is already inactive.")

    assignment.is_active = False
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment

def get_staff_assignments_for_lane(db: Session, lane_id: int, tenant_id: int, only_active: bool = True) -> List[StaffAssignment]:
    """
    Retrieves staff assignments for a specific lane. Eager loads user details.

    Args:
        db: SQLAlchemy database session.
        lane_id: ID of the lane.
        tenant_id: ID of the tenant.
        only_active: If True, only return active assignments.

    Returns:
        A list of StaffAssignment objects with User details populated.
    """
    query = db.query(StaffAssignment).options(selectinload(StaffAssignment.user)).filter(
        StaffAssignment.lane_id == lane_id,
        StaffAssignment.tenant_id == tenant_id
    )
    if only_active:
        query = query.filter(StaffAssignment.is_active == True)
    return query.all()
