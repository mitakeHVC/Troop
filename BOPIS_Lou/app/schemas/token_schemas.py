from pydantic import BaseModel
from typing import Optional
import datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer" # Default to bearer
    refresh_token: Optional[str] = None # Include refresh token

class TokenPayload(BaseModel):
    sub: Optional[str] = None # Subject (user identifier, e.g., username or user_id as string)
    role: Optional[str] = None
    tenant_id: Optional[int] = None
    exp: Optional[datetime.datetime] = None
    type: str = "access" # To distinguish between access and refresh tokens

class RefreshTokenRequest(BaseModel):
    refresh_token: str
