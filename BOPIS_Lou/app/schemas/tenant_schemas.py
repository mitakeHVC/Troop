from pydantic import BaseModel
import datetime
from typing import List # For future use if embedding users/products

class TenantBase(BaseModel):
    name: str

class TenantCreate(TenantBase):
    pass

class TenantResponse(TenantBase):
    id: int
    created_at: datetime.datetime
    # Add other fields if needed, e.g., lists of users, products (consider pagination)

    class Config:
        orm_mode = True
