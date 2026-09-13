from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password
from app.api.deps import require_permission
from app.models.auth import User, AuditLogEntry
from app.models.reference import DataSource
from app.schemas.auth import UserOut, UserCreate, UserRoleUpdate

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


@router.patch("/users/{user_id}/toggle-active", response_model=UserOut)

def toggle_user_active(user_id: int, db: Session = Depends(get_db), current_user=Depends(require_permission("manage_users"))):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="cannot_toggle_self")
    user.is_active = not user.is_active
    db.add(AuditLogEntry(user_id=current_user.id, user_email=current_user.email,
                          action="TOGGLE_USER_ACTIVE", entity_type="User",
                          entity_id=str(user_id), details={"is_active": user.is_active}))
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/role", response_model=UserOut)
def update_user_role(user_id: int, payload: UserRoleUpdate, db: Session = Depends(get_db), current_user=Depends(require_permission("manage_users"))):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    if payload.role not in ("ADMIN", "ANALYST", "VIEWER"):
        raise HTTPException(status_code=400, detail="invalid_role")
    user.role = payload.role
    db.add(AuditLogEntry(user_id=current_user.id, user_email=current_user.email,
                          action="UPDATE_USER_ROLE", entity_type="User",
                          entity_id=str(user_id), details={"new_role": payload.role}))
    db.commit()
    db.refresh(user)
    return user


@router.post("/calibrate-weights-dgca")
def calibrate_weights_dgca(db: Session = Depends(get_db), current_user=Depends(require_permission("manage_route_weights"))):
    from app.models.reference import Route
    from app.models.dgca import DgcaTrafficRecord
    from app.services.dgca_service import get_calibrated_route_weights
    from app.services.scheduler_service import run_dgca_traffic_refresh

    # Ensure the DGCA traffic table is fresh before calibrating (idempotent
    # upsert of the official bundled dataset; entirely local, no network).
    refreshed = False
    try:
        run_dgca_traffic_refresh()
        refreshed = True
    except Exception:  # noqa: BLE001 - calibration must never fail on refresh
        pass

    traffic_count = db.query(DgcaTrafficRecord).count()

    active_routes = db.query(Route).filter(Route.active == True).all()  # noqa: E712
    route_keys = [r.route_key for r in active_routes]
    calibrated = get_calibrated_route_weights(route_keys)

    for r in active_routes:
        if r.route_key in calibrated:
            r.weight = calibrated[r.route_key]

    db.add(AuditLogEntry(user_id=current_user.id, user_email=current_user.email,
                          action="CALIBRATE_ROUTE_WEIGHTS_DGCA", entity_type="Route",
                          details={"calibrated_routes_count": len(active_routes),
                                   "traffic_records": traffic_count}))
    db.commit()
    return {
        "status": "success",
        "calibrated_weights": calibrated,
        "traffic_source": "dgca_route_traffic" if refreshed else "bundled_dataset",
        "traffic_records": traffic_count,
    }


@router.get("/dgca-traffic")
def list_dgca_traffic(db: Session = Depends(get_db), _=Depends(require_permission("manage_route_weights"))):
    from app.models.dgca import DgcaTrafficRecord

    rows = db.query(DgcaTrafficRecord).order_by(DgcaTrafficRecord.passengers.desc()).all()
    return {
        "available": bool(rows),
        "period": rows[0].period if rows else None,
        "source": rows[0].source if rows else None,
        "count": len(rows),
        "records": [
            {
                "route_key": r.route_key,
                "origin": r.origin,
                "destination": r.destination,
                "passengers": r.passengers,
                "source_url": r.source_url,
                "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            }
            for r in rows
        ],
    }


