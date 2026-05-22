from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.evidence import Evidence, EvidenceReuseFlag
from app.repositories.base import BaseRepository

class EvidenceRepository(BaseRepository[Evidence]):
    def __init__(self, session: AsyncSession):
        super().__init__(Evidence, session)

    async def get_by_hash(self, content_hash: str) -> Sequence[Evidence]:
        from sqlalchemy.orm import selectinload
        query = select(self.model).where(self.model.content_hash == content_hash).options(selectinload(self.model.claim))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def add_reuse_flag(self, flag: EvidenceReuseFlag):
        self.session.add(flag)
        await self.session.flush()

    async def get_reuse_flags(self, evidence_id: int) -> Sequence[EvidenceReuseFlag]:
        query = select(EvidenceReuseFlag).where(EvidenceReuseFlag.evidence_id == evidence_id)
        result = await self.session.execute(query)
        return result.scalars().all()
