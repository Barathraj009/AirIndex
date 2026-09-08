from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.models.reference import Route, Airline
from app.models.auth import AuditLogEntry
from app.schemas.reference import RouteOut, RouteIn, RouteWeightUpdate, AirlineOut

router = APIRouter(prefix="/api", tags=["reference"])


@router.get("/routes", response_model=list[RouteOut])
def list_routes(db: Session = Depends(get_db), _=Depends(require_permission("view_dashboard"))):
    return db.query(Route).all()


@router.post("/routes", response_model=RouteOut)
def create_route(payload: RouteIn, db: Session = Depends(get_db),
                  current_user=Depends(require_permission("manage_routes"))):
    existing = db.query(Route).filter(Route.origin == payload.origin,
                                       Route.destination == payload.destination).first()
    if existing:
        raise HTTPException(status_code=409, detail="route_already_exists")
    route = Route(**payload.model_dump())
    db.add(route)
    db.add(AuditLogEntry(user_id=current_user.id, user_email=current_user.email,
                          action="CREATE_ROUTE", entity_type="Route",
                          details=payload.model_dump()))
    db.commit()
    db.refresh(route)
    return route


@router.patch("/routes/{route_id}/weight", response_model=RouteOut)
def update_route_weight(route_id: int, payload: RouteWeightUpdate, db: Session = Depends(get_db),
                         current_user=Depends(require_permission("manage_route_weights"))):
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="route_not_found")
    old_weight = route.weight
    route.weight = payload.weight
    db.add(AuditLogEntry(user_id=current_user.id, user_email=current_user.email,
                          action="UPDATE_ROUTE_WEIGHT", entity_type="Route", entity_id=str(route_id),
                          details={"old_weight": old_weight, "new_weight": payload.weight}))
    db.commit()
    db.refresh(route)
    return route


@router.delete("/routes/{route_id}")
def deactivate_route(route_id: int, db: Session = Depends(get_db),
                      current_user=Depends(require_permission("manage_routes"))):
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="route_not_found")
    route.active = False
    db.add(AuditLogEntry(user_id=current_user.id, user_email=current_user.email,
                          action="DEACTIVATE_ROUTE", entity_type="Route", entity_id=str(route_id)))
    db.commit()
    return {"status": "deactivated", "route_id": route_id}


@router.get("/airlines", response_model=list[AirlineOut])
def list_airlines(db: Session = Depends(get_db), _=Depends(require_permission("view_dashboard"))):
    return db.query(Airline).all()
