from fastapi import APIRouter, Depends, HTTPException
from typing import List, Any
from app.api.dependencies import get_audit_repo, get_current_user, RoleChecker
from app.models.enums import UserRole
from app.models.user import User

router = APIRouter()

@router.get("/claim/{claim_id}")
async def get_claim_audit(
    claim_id: int,
    audit_repo = Depends(get_audit_repo),
    current_user: User = Depends(get_current_user)
):
    # RBAC: Only Reviewers and Controllers can see full audit logs
    if current_user.role == UserRole.EMPLOYEE:
        # Check if they own the claim?
        # Typically Audit is for internal compliance.
        raise HTTPException(status_code=403, detail="Audit logs are restricted to Reviewers and Controllers")
        
    return await audit_repo.get_by_claim(claim_id)

@router.get("/")
async def list_audit_logs(
    audit_repo = Depends(get_audit_repo),
    current_user: User = Depends(RoleChecker([UserRole.CONTROLLER]))
):
    return await audit_repo.list_all()
