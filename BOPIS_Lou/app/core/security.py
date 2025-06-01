from datetime import datetime, timedelta
from typing import Optional, Any, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
from app.schemas.token_schemas import TokenPayload

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS
SECRET_KEY = settings.SECRET_KEY # Main secret key
# Consider a separate REFRESH_SECRET_KEY if you want to invalidate them separately
# REFRESH_SECRET_KEY = settings.REFRESH_SECRET_KEY

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(subject: Union[str, Any], role: str, tenant_id: Optional[int], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject), "type": "access", "role": role, "tenant_id": tenant_id}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(subject: Union[str, Any], role: str, tenant_id: Optional[int], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    # Role/tenant_id in refresh token is optional, could be re-queried from DB using user ID (sub)
    # Including them for consistency or if direct use without DB lookup is planned for refresh logic.
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh", "role": role, "tenant_id": tenant_id}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM) # Use same secret or specific refresh secret
    return encoded_jwt

def verify_token(token: str) -> Optional[TokenPayload]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Manually handle optional exp for robust parsing before creating TokenPayload
        # Pydantic might raise validation error if 'exp' is present but None in payload and model requires datetime
        exp_timestamp = payload.get("exp")
        if exp_timestamp is None: # Should not happen for our created tokens
            return None

        # Ensure 'exp' is a datetime object before creating TokenPayload
        # jwt.decode should return 'exp' as datetime if it was encoded as such
        # but if it's from an external source or malformed, it might be int/float
        if not isinstance(exp_timestamp, datetime):
             # Attempt to convert if it's a timestamp number
            try:
                exp_datetime = datetime.utcfromtimestamp(exp_timestamp)
                payload["exp"] = exp_datetime
            except (TypeError, ValueError):
                 return None # Cannot parse exp

        token_data = TokenPayload(**payload)

        # Check expiry after successful parsing
        if datetime.utcnow() > token_data.exp: # type: ignore
            return None # Token expired

        return token_data
    except JWTError:
        return None
    except Exception: # Catch any other parsing/validation errors with TokenPayload
        return None
