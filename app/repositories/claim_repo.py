from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.claim import Claim, ClaimStatusHistory, ReviewerComment
from app.repositories.base import BaseRepository

class ClaimRepository(BaseRepository[Claim]):
    def __init__(self, session: AsyncSession):
        super().__init__(Claim, session)

    async def get_with_lock(self, id: int) -> Optional[Claim]:
        """
        Optional: If we wanted pessimistic locking, we'd use .with_for_update() here.
        Since we approved Optimistic Locking, we'll just fetch normally and let
        SQLAlchemy's versioning handle it during flush/commit.
        """
        return await self.get(id)

    async def get_status_history(self, claim_id: int) -> Sequence[ClaimStatusHistory]:
        query = select(ClaimStatusHistory).where(ClaimStatusHistory.claim_id == claim_id).order_by(ClaimStatusHistory.changed_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def add_status_history(self, history: ClaimStatusHistory):
        self.session.add(history)
        await self.session.flush()

    async def add_comment(self, comment: ReviewerComment):
        self.session.add(comment)
        await self.session.flush()
