from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional, List # Added List just in case for future extensions
from app.db.session import get_db
from app.models.sql_models import User
from app.models.sql_models import UserRole as DBUserRoleEnum
from app.schemas.pos_schemas import POSOrderCreateRequest
from app.schemas.order_schemas import OrderResponse # Re-use OrderResponse
from app.services import order_service
from app.api import deps

router = APIRouter()

def get_pos_staff_user(current_user: User = Depends(deps.get_current_user)) -> User:
    # Define which roles can perform POS operations
    allowed_roles = [DBUserRoleEnum.counter, DBUserRoleEnum.tenant_admin, DBUserRoleEnum.super_admin]
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not have POS privileges.")
    if not current_user.tenant_id and current_user.role != DBUserRoleEnum.super_admin: # POS staff must be in a tenant
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff must be associated with a tenant for POS operations.")
    return current_user

@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_new_pos_order(
    pos_order_in: POSOrderCreateRequest,
    # Idempotency key can also be passed as a header
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"), # Use Header for idempotency key
    db: Session = Depends(get_db),
    staff_user: User = Depends(get_pos_staff_user)
):
    # If idempotency_key from header is preferred over body, or to reconcile if both present:
    if idempotency_key: # Header takes precedence if provided
        pos_order_in.idempotency_key = idempotency_key

    tenant_id_context = staff_user.tenant_id
    if staff_user.role == DBUserRoleEnum.super_admin:
        # Super admin needs to operate within a tenant context for POS.
        # This might require passing tenant_id in the request body or using a tenant-specific path.
        # For now, if SA, they must have a tenant_id associated or it's an error.
        # The get_pos_staff_user dependency already checks if SA has tenant_id (currently it doesn't enforce SA to have one).
        # Let's refine: SA cannot create POS orders through this generic endpoint without a clear tenant context.
        # This should ideally be handled by `get_pos_staff_user` or by having `pos_order_in` include `tenant_id` for SA.
        # For this iteration, if it's SA and tenant_id is None on staff_user, it's an issue.
        if not tenant_id_context:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super admin POS operations require explicit tenant context (e.g. staff user having a tenant_id or tenant_id in request).")

    if not tenant_id_context: # Should be caught by dependency for counter/tenant_admin
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not associated with a tenant for POS operation.")

    # The service function `create_pos_order` will use staff_user.tenant_id
    try:
        created_order = order_service.create_pos_order(db, pos_order_in=pos_order_in, staff_user=staff_user)
        return created_order
    except HTTPException as e:
        raise e
    except Exception as e_internal:
        # Log e_internal
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while creating the POS order.")
