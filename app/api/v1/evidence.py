from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from app.models.evidence import Evidence
from app.api.dependencies import (
    get_evidence_service, 
    get_evidence_repo,
    get_current_user,
    get_ai_service,
    RoleChecker
)
from app.services.evidence_service import EvidenceService
from app.repositories.evidence_repo import EvidenceRepository
from app.core.exceptions import InvalidStateTransitionError, PermissionDeniedError
from app.models.enums import UserRole
from app.models.user import User

router = APIRouter()

@router.delete("/claims/{claim_id}/evidence/{evidence_id}")
async def delete_claim_evidence(
    claim_id: int,
    evidence_id: int,
    service: EvidenceService = Depends(get_evidence_service),
    current_user: User = Depends(get_current_user)
):
    """
    Delete evidence associated with a specific claim.
    """
    try:
        path, evidence = await service.get_evidence_file(evidence_id)
        if evidence.claim_id != claim_id:
            raise HTTPException(status_code=400, detail="Evidence does not belong to this claim")
            
        await service.delete_evidence(evidence_id, current_user.id)
        return {"status": "EVIDENCE_DELETED"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvalidStateTransitionError, PermissionDeniedError) as e:
        raise HTTPException(status_code=409 if isinstance(e, InvalidStateTransitionError) else 403, detail=str(e))

from app.schemas.claim import EvidenceReuseFlagCreate

@router.post("/claims/{claim_id}/flag-evidence-reuse", status_code=status.HTTP_201_CREATED)
async def flag_evidence_reuse(
    claim_id: int,
    flag_in: EvidenceReuseFlagCreate,
    service: EvidenceService = Depends(get_evidence_service),
    current_user: User = Depends(RoleChecker([UserRole.REVIEWER, UserRole.CONTROLLER]))
):
    """
    Reviewer flags that evidence was reused and assesses if it's legitimate.
    """
    from app.models.evidence import EvidenceReuseFlag
    from app.models.enums import AuditAction
    
    try:
        # Validate evidence belongs to the primary claim (claim_id from URL)
        path, evidence = await service.get_evidence_file(flag_in.evidence_id)
        if evidence.claim_id != claim_id:
            raise HTTPException(status_code=400, detail="Evidence does not belong to the primary claim")
            
        # Create the manual flag
        flag = EvidenceReuseFlag(
            evidence_id=flag_in.evidence_id,
            primary_claim_id=claim_id,
            secondary_claim_id=flag_in.secondary_claim_id,
            is_legitimate=flag_in.is_legitimate,
            flagged_by_id=current_user.id,
            reviewer_notes=flag_in.reviewer_notes
        )
        
        await service.evidence_repo.add_reuse_flag(flag)
        
        # Log manual flagging event
        await service.audit_service.log_action(
            actor_id=current_user.id,
            action=AuditAction.EVIDENCE_REUSE_FLAGGED,
            claim_id=claim_id,
            new_value={
                "evidence_id": flag_in.evidence_id,
                "secondary_claim_id": flag_in.secondary_claim_id,
                "is_legitimate": flag_in.is_legitimate,
                "manual_assessment": True
            }
        )
        await service.evidence_repo.session.commit()
        
        return {
            "flag_id": flag.id,
            "status": "FLAG_CREATED"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{claim_id}/upload")
async def upload_evidence(
    claim_id: int,
    file: UploadFile = File(...),
    service: EvidenceService = Depends(get_evidence_service),
    current_user: User = Depends(get_current_user)
):
    try:
        content = await file.read()
        evidence, flags = await service.upload_evidence(
            claim_id=claim_id,
            user_id=current_user.id,
            file_name=file.filename,
            content=content,
            mime_type=file.content_type
        )
        return {
            "evidence_id": evidence.id,
            "file_name": evidence.file_name,
            "content_hash": evidence.content_hash,
            "flags_detected": len(flags) > 0
        }
    except (InvalidStateTransitionError, PermissionDeniedError) as e:
        raise HTTPException(status_code=409 if isinstance(e, InvalidStateTransitionError) else 403, detail=str(e))

@router.get("/claim/{claim_id}")
async def list_evidence(
    claim_id: int,
    evidence_repo: EvidenceRepository = Depends(get_evidence_repo),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy import select
    from app.models.evidence import Evidence
    from app.models.claim import Claim
    
    # Check if user has access to this claim
    query_claim = select(Claim).where(Claim.id == claim_id)
    result_claim = await evidence_repo.session.execute(query_claim)
    claim = result_claim.scalars().first()
    
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    if current_user.role == UserRole.EMPLOYEE and claim.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this claim's evidence")
        
    query = select(Evidence).where(Evidence.claim_id == claim_id)
    result = await evidence_repo.session.execute(query)
    return result.scalars().all()

@router.delete("/{evidence_id}")
async def remove_evidence(
    evidence_id: int,
    evidence_service: EvidenceService = Depends(get_evidence_service),
    current_user: User = Depends(get_current_user)
):
    try:
        await evidence_service.delete_evidence(evidence_id, current_user.id)
        return {"status": "DELETED"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvalidStateTransitionError, PermissionDeniedError) as e:
        raise HTTPException(status_code=409 if isinstance(e, InvalidStateTransitionError) else 403, detail=str(e))

@router.get("/{evidence_id}/download")
async def download_evidence(
    evidence_id: int,
    evidence_service: EvidenceService = Depends(get_evidence_service),
    evidence_repo: EvidenceRepository = Depends(get_evidence_repo),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy.orm import selectinload
    query = select(Evidence).where(Evidence.id == evidence_id).options(selectinload(Evidence.claim))
    result = await evidence_repo.session.execute(query)
    evidence = result.scalars().first()

    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
        
    # RBAC - claim is now safely loaded
    claim = evidence.claim
    if current_user.role == UserRole.EMPLOYEE and claim.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to download this evidence")
        
    file_path, evidence = await evidence_service.get_evidence_file(evidence_id)
    return FileResponse(
        path=file_path,
        filename=evidence.file_name,
        media_type=evidence.mime_type
    )

@router.get("/{evidence_id}/reuse")
async def get_evidence_reuse(
    evidence_id: int,
    evidence_repo: EvidenceRepository = Depends(get_evidence_repo),
    current_user: User = Depends(RoleChecker([UserRole.REVIEWER, UserRole.CONTROLLER]))
):
    evidence = await evidence_repo.get(evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
        
    flags = await evidence_repo.get_reuse_flags(evidence_id)
    return {
        "evidence_id": evidence_id,
        "content_hash": evidence.content_hash,
        "flags": flags
    }

@router.post("/{evidence_id}/ai-verify")
async def verify_evidence_amount(
    evidence_id: int,
    service: EvidenceService = Depends(get_evidence_service),
    ai_service: Any = Depends(get_ai_service),
    current_user: User = Depends(get_current_user)
):
    """
    AI-powered check to extract total from receipt and compare with claim amount.
    """
    from app.models.enums import AuditAction
    
    try:
        path, evidence, claim = await service.get_evidence_file(evidence_id)
        
        # Call Real Gemini AI Service
        ai_result = await ai_service.analyze_receipt(path, float(claim.amount))
        
        # Log AI action to audit trail
        await service.audit_service.log_action(
            actor_id=current_user.id,
            action=AuditAction.EXTERNAL_VALIDATION_TRIGGERED,
            claim_id=claim.id,
            new_value={
                "evidence_id": evidence_id,
                "ai_result": ai_result
            }
        )
        await service.evidence_repo.session.commit()
        
        return ai_result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
