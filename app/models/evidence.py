from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base

class Evidence(Base):
    __tablename__ = "evidence"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    file_name = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    content_hash = Column(String, index=True, nullable=False)
    mime_type = Column(String, nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    claim = relationship("Claim", back_populates="evidence")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])
    flags = relationship("EvidenceReuseFlag", back_populates="evidence", cascade="all, delete-orphan")

class EvidenceReuseFlag(Base):
    __tablename__ = "evidence_reuse_flags"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=False)
    primary_claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    secondary_claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    flagged_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    flagged_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_legitimate = Column(Boolean, nullable=True) # True = Legitimate reuse, False = Fraud suspected
    reviewer_notes = Column(String, nullable=True)
    resolved = Column(Boolean, default=False, nullable=False)
    resolution_notes = Column(String, nullable=True)
    
    evidence = relationship("Evidence", back_populates="flags")
    primary_claim = relationship("Claim", foreign_keys=[primary_claim_id])
    secondary_claim = relationship("Claim", foreign_keys=[secondary_claim_id])
    flagged_by = relationship("User", foreign_keys=[flagged_by_id])
