from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from app.db.base import Base
from app.models.enums import AuditAction

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(Enum(AuditAction), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)

    # Relationships
    claim = relationship("Claim", lazy="noload", viewonly=True)
    actor = relationship("User", lazy="noload", viewonly=True)

    # NOTE: App-level logic and database permissions should enforce that this table is INSERT-only (append-only).
