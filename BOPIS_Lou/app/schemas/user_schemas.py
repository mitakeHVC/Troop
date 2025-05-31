from pydantic import BaseModel, EmailStr
from typing import Optional
import datetime
import enum # Required for UserRoleEnum definition

# Import the DB model UserRole to ensure consistency, but define a string-based one for Pydantic
# from app.models.sql_models import UserRole as DBUserRole

# For Pydantic validation with string enums
class UserRoleEnum(str, enum.Enum):
    customer = "customer"
    picker = "picker"
    counter = "counter"
    tenant_admin = "tenant_admin"
    super_admin = "super_admin"

class UserBase(BaseModel):
    username: str
    email: EmailStr
    role: UserRoleEnum # Uses the Pydantic string-based enum

class UserCreate(UserBase):
    password: str
    tenant_id: Optional[int] = None # Required for non-super_admin roles

class UserLogin(BaseModel):
    username: str # Can be username or email
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime.datetime
    tenant_id: Optional[int] = None # Explicitly make it optional for super_admin, etc.

    class Config:
        orm_mode = True

# New Schemas to add
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    # For password update, typically require current_password
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class StaffCreate(UserCreate): # Inherits from UserCreate
    # Role is assigned to picker, counter, or tenant_admin by the creating Tenant Admin
    # tenant_id is derived from the path parameter for the endpoint when creating.
    # UserCreate already has 'role: UserRoleEnum' and 'tenant_id: Optional[int]'
    pass

class StaffResponse(UserResponse): # UserResponse is suitable
    pass

class StaffUpdate(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[UserRoleEnum] = None # e.g. picker to counter
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    # Password reset for staff by admin might be a separate flow or require specific privileges
