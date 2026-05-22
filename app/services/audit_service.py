from typing import Optional, Any
from app.models.audit import AuditLog
from app.models.enums import AuditAction
from app.repositories.audit_repo import AuditRepository

class AuditService:
    def __init__(self, audit_repo: AuditRepository):
        self.audit_repo = audit_repo

    async def log_action(
        self,
        actor_id: int,
        action: AuditAction,
        claim_id: Optional[int] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        metadata: Optional[dict] = None
    ):
        audit_entry = AuditLog(
            actor_id=actor_id,
            action=action,
            claim_id=claim_id,
            old_value=old_value,
            new_value=new_value,
            metadata_=metadata
        )
        return await self.audit_repo.create(audit_entry)
