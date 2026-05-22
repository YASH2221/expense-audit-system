from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.repositories.claim_repo import ClaimRepository
from app.repositories.audit_repo import AuditRepository
from app.repositories.evidence_repo import EvidenceRepository
from app.repositories.amendment_repo import AmendmentRepository
from app.services.audit_service import AuditService
from app.services.claim_service import ClaimService
from app.services.evidence_service import EvidenceService
from app.models.user import User
from app.models.enums import UserRole

def get_claim_repo(db: AsyncSession = Depends(get_db)) -> ClaimRepository:
    return ClaimRepository(db)

def get_audit_repo(db: AsyncSession = Depends(get_db)) -> AuditRepository:
    return AuditRepository(db)

def get_evidence_repo(db: AsyncSession = Depends(get_db)) -> EvidenceRepository:
    return EvidenceRepository(db)

def get_amendment_repo(db: AsyncSession = Depends(get_db)) -> AmendmentRepository:
    return AmendmentRepository(db)

def get_audit_service(audit_repo: AuditRepository = Depends(get_audit_repo)) -> AuditService:
    return AuditService(audit_repo)

def get_claim_service(
    claim_repo: ClaimRepository = Depends(get_claim_repo),
    audit_service: AuditService = Depends(get_audit_service),
    amendment_repo: AmendmentRepository = Depends(get_amendment_repo)
) -> ClaimService:
    return ClaimService(claim_repo, audit_service, amendment_repo)

def get_evidence_service(
    evidence_repo: EvidenceRepository = Depends(get_evidence_repo),
    audit_service: AuditService = Depends(get_audit_service)
) -> EvidenceService:
    return EvidenceService(evidence_repo, audit_service)

def get_ai_service():
    from app.services.ai_service import AIService
    return AIService()

async def get_current_user(
    user_id: int = Header(..., alias="X-User-Id"),
    db: AsyncSession = Depends(get_db)
) -> User:
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

class RoleChecker:
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Role {user.role} not permitted for this action"
            )
        return user
