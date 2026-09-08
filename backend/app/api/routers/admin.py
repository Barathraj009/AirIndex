from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password
from app.api.deps import require_permission
from app.models.auth import User, AuditLogEntry
from app.models.reference import DataSource
from app.schemas.auth import UserOut, UserCreate

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit-log")
def audit_log(limit: int = 100, db: Session = Depends(get_db),
              _=Depends(require_permission("view_audit_log"))):
    rows = db.query(AuditLogEntry).order_by(AuditLogEntry.timestamp.desc()).limit(limit).all()
    return [
        {"id": r.id, "user_email": r.user_email, "action": r.action, "entity_type": r.entity_type,
         "entity_id": r.entity_id, "details": r.details, "timestamp": r.timestamp}
        for r in rows
    ]


@router.get("/data-sources")
def list_data_sources(db: Session = Depends(get_db), _=Depends(require_permission("manage_data_sources"))):
    return db.query(DataSource).all()


@router.patch("/data-sources/{source_id}/toggle")
def toggle_data_source(source_id: int, db: Session = Depends(get_db),
                        current_user=Depends(require_permission("manage_data_sources"))):
    source = db.get(DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    source.active = not source.active
    db.add(AuditLogEntry(user_id=current_user.id, user_email=current_user.email,
                          action="TOGGLE_DATA_SOURCE", entity_type="DataSource",
                          entity_id=str(source_id), details={"active": source.active}))
    db.commit()
    return {"id": source.id, "name": source.name, "active": source.active}


@router.post("/users", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                 current_user=Depends(require_permission("manage_users"))):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="user_already_exists")
    user = User(email=payload.email, hashed_password=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.add(AuditLogEntry(user_id=current_user.id, user_email=current_user.email,
                          action="CREATE_USER", entity_type="User", details={"email": payload.email, "role": payload.role}))
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_permission("manage_users"))):
    return db.query(User).all()
