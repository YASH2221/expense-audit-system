from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Any, Optional
from app.schemas.claim import (
    ClaimCreate, 
    ClaimResponse, 
    ReviewDecision, 
    ClaimStatusHistoryResponse, 
    ClaimUpdate, 
    ReviewCommentCreate
)
from app.repositories.claim_repo import ClaimRepository
from app.repositories.evidence_repo import EvidenceRepository
from app.api.dependencies import (
    get_claim_service, 
    get_claim_repo, 
    get_audit_repo, 
    get_amendment_repo,
    get_evidence_service,
    get_current_user,
    RoleChecker
)
from app.services.claim_service import ClaimService
from app.services.evidence_service import EvidenceService
from app.core.exceptions import (
    InvalidStateTransitionError, 
    ConcurrencyConflictError, 
    InsufficientEvidenceError,
    PermissionDeniedError
)
from app.models.enums import ClaimStatus, UserRole
from app.models.user import User

router = APIRouter()

@router.post("/", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def create_claim(
    claim_in: ClaimCreate,
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(get_current_user)
):
    try:
        return await service.create_claim(
            employee_id=current_user.id,
            amount=claim_in.amount,
            description=claim_in.description,
            purpose=claim_in.purpose
        )
    except ConcurrencyConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.get("/", response_model=List[ClaimResponse])
async def list_claims(
    status: Optional[ClaimStatus] = None,
    employee_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    claim_repo: ClaimRepository = Depends(get_claim_repo),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy import select
    query = select(claim_repo.model).offset(skip).limit(limit)
    
    # RBAC: Employees only see their own claims
    if current_user.role == UserRole.EMPLOYEE:
        query = query.where(claim_repo.model.employee_id == current_user.id)
    else:
        # Reviewers/Controllers can filter by employee_id if provided
        if employee_id:
            query = query.where(claim_repo.model.employee_id == employee_id)
            
    if status:
        query = query.where(claim_repo.model.status == status)
        
    result = await claim_repo.session.execute(query)
    return result.scalars().all()

@router.patch("/{claim_id}", response_model=ClaimResponse)
async def update_claim(
    claim_id: int,
    claim_in: ClaimUpdate,
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(get_current_user)
):
    try:
        return await service.update_claim(claim_id, current_user.id, claim_in.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvalidStateTransitionError, PermissionDeniedError) as e:
        raise HTTPException(status_code=409 if isinstance(e, InvalidStateTransitionError) else 403, detail=str(e))

@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: int,
    claim_repo: ClaimRepository = Depends(get_claim_repo),
    current_user: User = Depends(get_current_user)
):
    claim = await claim_repo.get(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    # RBAC check
    if current_user.role == UserRole.EMPLOYEE and claim.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this claim")
        
    return claim

@router.post("/{claim_id}/submit", response_model=ClaimResponse)
async def submit_claim(
    claim_id: int,
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(get_current_user)
):
    try:
        return await service.submit_claim(claim_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvalidStateTransitionError, ConcurrencyConflictError, InsufficientEvidenceError, PermissionDeniedError) as e:
        status_code = 409
        if isinstance(e, InsufficientEvidenceError): status_code = 400
        if isinstance(e, PermissionDeniedError): status_code = 403
        raise HTTPException(status_code=status_code, detail=str(e))

@router.post("/{claim_id}/review", response_model=ClaimResponse)
async def review_claim(
    claim_id: int,
    review_in: ReviewDecision,
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(RoleChecker([UserRole.REVIEWER]))
):
    try:
        if review_in.decision == ClaimStatus.APPROVED:
            return await service.approve_claim(claim_id, current_user.id, review_in.remarks)
        elif review_in.decision == ClaimStatus.CHANGES_REQUESTED:
            return await service.request_changes(claim_id, current_user.id, review_in.remarks)
        elif review_in.decision == ClaimStatus.REJECTED:
            return await service.reject_claim(claim_id, current_user.id, review_in.remarks)
        else:
            raise HTTPException(status_code=400, detail="Invalid decision")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvalidStateTransitionError, ConcurrencyConflictError, InsufficientEvidenceError, PermissionDeniedError) as e:
        status_code = 409
        if isinstance(e, InsufficientEvidenceError): status_code = 400
        if isinstance(e, PermissionDeniedError): status_code = 403
        raise HTTPException(status_code=status_code, detail=str(e))

@router.post("/{claim_id}/finalize", response_model=ClaimResponse)
async def finalize_claim(
    claim_id: int,
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(RoleChecker([UserRole.CONTROLLER]))
):
    try:
        return await service.finalize_claim(claim_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvalidStateTransitionError, ConcurrencyConflictError) as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.get("/{claim_id}/history")
async def get_claim_history(
    claim_id: int,
    claim_repo: ClaimRepository = Depends(get_claim_repo),
    audit_repo: Any = Depends(get_audit_repo),
    amendment_repo: Any = Depends(get_amendment_repo),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from app.models.claim import Claim
    
    query = select(Claim).where(Claim.id == claim_id).options(selectinload(Claim.comments))
    result = await claim_repo.session.execute(query)
    claim = result.scalars().first()
    
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    # RBAC: Employees can only view history of their own claims
    if current_user.role == UserRole.EMPLOYEE and claim.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this claim history")
        
    status_history = await claim_repo.get_status_history(claim_id)
    audit_trail = await audit_repo.get_by_claim(claim_id)
    amendments = await amendment_repo.get_by_original_claim(claim_id)
    
    return {
        "claim_id": claim_id,
        "current_status": claim.status,
        "timeline": status_history,
        "audit_logs": audit_trail,
        "amendments": amendments,
        "reviewer_comments": claim.comments
    }

@router.post("/{claim_id}/comment")
async def add_comment(
    claim_id: int,
    comment_in: ReviewCommentCreate,
    claim_repo: ClaimRepository = Depends(get_claim_repo),
    current_user: User = Depends(RoleChecker([UserRole.REVIEWER, UserRole.CONTROLLER]))
):
    from app.models.claim import ReviewerComment
    
    comment_text = comment_in.comment
    if not comment_text.strip():
        raise HTTPException(status_code=400, detail="Comment text cannot be empty")
        
    comment = ReviewerComment(
        claim_id=claim_id,
        reviewer_id=current_user.id,
        comment_text=comment_text
    )
    await claim_repo.add_comment(comment)
    await claim_repo.session.commit()
    
    return {"status": "COMMENT_ADDED"}
