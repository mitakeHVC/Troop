from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.sql_models import Tenant
from app.schemas.tenant_schemas import TenantCreate

def get_tenant_by_id(db: Session, tenant_id: int) -> Optional[Tenant]:
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()

def get_tenant_by_name(db: Session, name: str) -> Optional[Tenant]:
    return db.query(Tenant).filter(Tenant.name == name).first()

def get_tenants(db: Session, skip: int = 0, limit: int = 100) -> List[Tenant]:
    return db.query(Tenant).offset(skip).limit(limit).all()

def create_tenant(db: Session, tenant: TenantCreate) -> Tenant:
    db_tenant = Tenant(name=tenant.name)
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant
