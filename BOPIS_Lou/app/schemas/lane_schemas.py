from pydantic import BaseModel, Field
from typing import Optional, List
import datetime
import enum # Required for LaneStatusEnum
from app.schemas.user_schemas import UserResponse, UserRoleEnum # For staff details, UserRoleEnum for validation
# Assuming LaneStatus enum is available from models, create a Pydantic version
# from app.models.sql_models import LaneStatus as DBLaneStatusEnum # Not directly used, Pydantic enum defined below

class LaneStatusEnum(str, enum.Enum): # Pydantic version
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    BUSY = "BUSY"

class LaneBase(BaseModel):
    name: str

class LaneCreate(LaneBase):
    status: LaneStatusEnum = LaneStatusEnum.CLOSED # Default status on creation

class StaffAssignmentBasicInfo(BaseModel): # For brief info on LaneResponse (currently not used in LaneResponse per model)
    user_id: int
    username: str
    assigned_role: UserRoleEnum

    class Config:
        orm_mode = True

class LaneResponse(LaneBase):
    id: int
    tenant_id: int
    status: LaneStatusEnum # Uses Pydantic enum
    current_order_id: Optional[int] = None
    # staff_assignments: List[StaffAssignmentBasicInfo] = [] # Simplified view, can be added if needed
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True

class LaneUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[LaneStatusEnum] = None # Uses Pydantic enum

class LaneStatusUpdateRequest(BaseModel): # For staff to update their lane status
    status: LaneStatusEnum # Uses Pydantic enum

# Schemas for Staff Assignment to Lane (more detailed than StaffAssignmentBasicInfo)
class StaffAssignmentToLaneCreate(BaseModel):
    user_id: int # ID of the staff member (must have 'counter' role)
    # lane_id is from path, tenant_id from admin context

class StaffAssignmentResponse(BaseModel): # Full response for a staff assignment
    id: int
    user_id: int
    tenant_id: int
    assigned_role: UserRoleEnum # Uses Pydantic enum (should reflect actual role, e.g. 'counter')
    lane_id: Optional[int] = None # Should be populated for this context
    is_active: bool
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None
    user: UserResponse # Include full user details

    class Config:
        orm_mode = True
