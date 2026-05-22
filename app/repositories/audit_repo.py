from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog

class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.model = AuditLog

    async def create(self, audit_log: AuditLog) -> AuditLog:
        self.session.add(audit_log)
        await self.session.flush()
        return audit_log

    async def get_by_claim(self, claim_id: int) -> Sequence[AuditLog]:
        from sqlalchemy.orm import selectinload
        query = select(self.model).where(self.model.claim_id == claim_id).options(selectinload(self.model.claim)).order_by(self.model.timestamp.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_all(self, skip: int = 0, limit: int = 100) -> Sequence[AuditLog]:
        query = select(self.model).offset(skip).limit(limit).order_by(self.model.timestamp.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    # NOTE: No update or delete methods implemented to ensure append-only nature at app level.
