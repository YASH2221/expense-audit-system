from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base
from app.models.enums import ClaimStatus

class Claim(Base):
    __tablename__ = "claims"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(ClaimStatus), nullable=False, default=ClaimStatus.DRAFT)
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(String, nullable=True)
    purpose = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    finalized_at = Column(DateTime, nullable=True)
    
    # Optimistic locking
    version = Column(Integer, default=1, nullable=False)
    
    __mapper_args__ = {
        "version_id_col": version
    }

    # Relationships
    employee = relationship("User", foreign_keys=[employee_id], back_populates="claims")
    status_history = relationship("ClaimStatusHistory", back_populates="claim", cascade="all, delete-orphan")
    comments = relationship("ReviewerComment", back_populates="claim", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="claim", cascade="all, delete-orphan")

class ClaimStatusHistory(Base):
    __tablename__ = "claim_status_history"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    old_status = Column(Enum(ClaimStatus), nullable=True)
    new_status = Column(Enum(ClaimStatus), nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reason = Column(String, nullable=True)
    
    claim = relationship("Claim", back_populates="status_history")
    changed_by = relationship("User", foreign_keys=[changed_by_id])

class ReviewerComment(Base):
    __tablename__ = "reviewer_comments"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    comment_text = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    claim = relationship("Claim", back_populates="comments")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
