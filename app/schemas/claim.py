from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from app.models.enums import ClaimStatus

class ClaimBase(BaseModel):
    amount: Decimal
    description: str
    purpose: str

class ClaimCreate(ClaimBase):
    pass

class ClaimUpdate(BaseModel):
    amount: Optional[Decimal] = None
    description: Optional[str] = None
    purpose: Optional[str] = None

class ClaimResponse(ClaimBase):
    id: int
    employee_id: int
    status: ClaimStatus
    created_at: datetime
    updated_at: datetime
    finalized_at: Optional[datetime] = None
    version: int

    model_config = ConfigDict(from_attributes=True)

class ClaimStatusHistoryResponse(BaseModel):
    id: int
    old_status: Optional[ClaimStatus]
    new_status: ClaimStatus
    changed_by_id: int
    changed_at: datetime
    reason: Optional[str]

    model_config = ConfigDict(from_attributes=True)

class ReviewDecision(BaseModel):
    decision: ClaimStatus # APPROVED, CHANGES_REQUESTED, or REJECTED
    remarks: str

class ReviewCommentCreate(BaseModel):
    comment: str

class EvidenceReuseFlagCreate(BaseModel):
    evidence_id: int
    secondary_claim_id: int
    is_legitimate: bool
    reviewer_notes: str

