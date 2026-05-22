from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base

class Amendment(Base):
    __tablename__ = "amendments"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    original_claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    amendment_claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    controller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finalized_at = Column(DateTime, nullable=True)
    
    original_claim = relationship("Claim", foreign_keys=[original_claim_id])
    amendment_claim = relationship("Claim", foreign_keys=[amendment_claim_id])
    controller = relationship("User", foreign_keys=[controller_id])
