"""Users + audit log. Passwords are stored via
app.core.security.hash_password — never plaintext, never a reversible
encoding. Audit log backs spec section 10's "Maintain audit information
for important administrative actions." """

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="VIEWER")  # ADMIN / ANALYST / VIEWER
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    last_login_at = Column(DateTime(timezone=True), nullable=True)


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_email = Column(String(255), nullable=True)  # denormalized for durability if user is later deleted
    action = Column(String(100), nullable=False)  # e.g. "UPDATE_ROUTE_WEIGHT", "TRIGGER_INGESTION"
    entity_type = Column(String(50), nullable=True)  # e.g. "Route"
    entity_id = Column(String(50), nullable=True)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow, index=True)
