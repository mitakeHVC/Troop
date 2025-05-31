from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.sql_models import Lane, StaffAssignment, User, Order # Added Order
from app.models.sql_models import UserRole as DBUserRole
from app.models.sql_models import LaneStatus as DBLaneStatus
from app.schemas.lane_schemas import LaneCreate, LaneUpdate
from app.schemas.lane_schemas import LaneStatusEnum as PydanticLaneStatusEnum
from fastapi import HTTPException, status

def get_lane_by_id(db: Session, lane_id: int, tenant_id: int) -> Optional[Lane]:
    return db.query(Lane).filter(Lane.id == lane_id, Lane.tenant_id == tenant_id).first()

def get_lanes_by_tenant(
    db: Session,
    tenant_id: int,
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[PydanticLaneStatusEnum] = None
) -> List[Lane]:
    query = db.query(Lane).filter(Lane.tenant_id == tenant_id)
    if status_filter:
        query = query.filter(Lane.status == DBLaneStatus[status_filter.value])
    return query.order_by(Lane.name).offset(skip).limit(limit).all() # type: ignore

def create_lane(db: Session, lane_in: LaneCreate, tenant_id: int) -> Lane:
    db_lane = Lane(
        name=lane_in.name,
        status=DBLaneStatus[lane_in.status.value],
        tenant_id=tenant_id
    )
    db.add(db_lane)
    db.commit()
    db.refresh(db_lane)
    return db_lane

def update_lane_details(db: Session, db_lane: Lane, lane_in: LaneUpdate) -> Lane:
    update_data = lane_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value is not None:
            if isinstance(value, PydanticLaneStatusEnum):
                setattr(db_lane, field, DBLaneStatus[value.value])
            else:
                setattr(db_lane, field, value)
        else:
            setattr(db_lane, field, value)
    db.add(db_lane)
    db.commit()
    db.refresh(db_lane)
    return db_lane

def update_lane_status(db: Session, db_lane: Lane, new_status: PydanticLaneStatusEnum) -> Lane:
    db_lane.status = DBLaneStatus[new_status.value]
    if new_status == PydanticLaneStatusEnum.OPEN:
        db_lane.current_order_id = None

    db.add(db_lane)
    db.commit()
    db.refresh(db_lane)
    return db_lane

def delete_lane(db: Session, db_lane: Lane) -> Lane:
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

# --- New/Updated functions for Counter Workflow ---
def assign_order_to_lane(db: Session, lane: Lane, order: Order, counter_user: User) -> Lane:
    if lane.tenant_id != counter_user.tenant_id or order.tenant_id != counter_user.tenant_id: # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage resources outside of user's tenant.")
    if lane.status != DBLaneStatus.OPEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lane is not OPEN.")
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
    # db.refresh(order) # Order is not returned, but lane reflects the change
    return lane

def clear_lane_and_set_open(db: Session, lane_id: int, tenant_id: int) -> Optional[Lane]:
    lane = get_lane_by_id(db, lane_id=lane_id, tenant_id=tenant_id)
    if lane:
        # Potentially check if the order assigned is actually completed before clearing.
        # For now, assume this is called after order completion.
        lane.current_order_id = None # type: ignore
        lane.status = DBLaneStatus.OPEN # type: ignore
        db.add(lane)
        db.commit()
        db.refresh(lane)
        return lane
    return None
# --- End New/Updated functions ---

def assign_staff_to_lane(db: Session, lane: Lane, user_id: int, tenant_id: int) -> StaffAssignment:
    staff_user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
    if not staff_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found in this tenant.")
    if staff_user.role != DBUserRole.counter:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only 'counter' staff can be assigned to lanes.")

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
    query = db.query(StaffAssignment).filter(StaffAssignment.lane_id == lane_id, StaffAssignment.tenant_id == tenant_id)
    if only_active:
        query = query.filter(StaffAssignment.is_active == True) # type: ignore
    return query.all()
