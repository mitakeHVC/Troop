from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, verify_token
from app.schemas.token_schemas import TokenPayload
import time
from datetime import timedelta, datetime # Ensure datetime is imported for TokenPayload's exp field

# This is needed to ensure settings are loaded before security functions try to use them.
# In a real app, settings might be initialized differently or explicitly passed.
# For testing, ensure app.core.config.settings is usable.
from app.core.config import settings

def test_password_hashing():
    password = "testpassword"
    hashed_password = get_password_hash(password)
    assert verify_password(password, hashed_password)
    assert not verify_password("wrongpassword", hashed_password)

def test_jwt_creation_and_verification():
    user_id = 1
    role = "customer"
    tenant_id = 10

    # Ensure SECRET_KEY is set for JWT operations
    assert settings.SECRET_KEY != "YOUR_SECRET_KEY", "Default secret key should be changed for testing or production."

    access_token = create_access_token(subject=str(user_id), role=role, tenant_id=tenant_id)
    refresh_token = create_refresh_token(subject=str(user_id), role=role, tenant_id=tenant_id) # Role/tenant_id in refresh token might be optional

    assert access_token
    assert refresh_token

    # Verify access token
    payload_access = verify_token(access_token)
    assert payload_access is not None
    assert payload_access.sub == str(user_id)
    assert payload_access.role == role
    assert payload_access.tenant_id == tenant_id
    assert payload_access.type == "access"
    assert isinstance(payload_access.exp, datetime) # exp should be datetime

    # Verify refresh token
    payload_refresh = verify_token(refresh_token)
    assert payload_refresh is not None
    assert payload_refresh.sub == str(user_id)
    assert payload_refresh.role == role # Assuming role is also in refresh token
    assert payload_refresh.tenant_id == tenant_id # Assuming tenant_id is also in refresh token
    assert payload_refresh.type == "refresh"
    assert isinstance(payload_refresh.exp, datetime) # exp should be datetime

def test_expired_access_token():
    user_id = "test_user_expired"
    # Create token that expires almost immediately
    expires_delta = timedelta(seconds=1)
    token = create_access_token(subject=user_id, role="customer", tenant_id=1, expires_delta=expires_delta)

    time.sleep(1.1) # Wait for token to expire (increased slightly)

    payload = verify_token(token)
    assert payload is None # Should be None as it's expired
