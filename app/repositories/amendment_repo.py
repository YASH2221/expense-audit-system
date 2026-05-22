from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.amendment import Amendment
from app.repositories.base import BaseRepository

class AmendmentRepository(BaseRepository[Amendment]):
    def __init__(self, session: AsyncSession):
        super().__init__(Amendment, session)

    async def get_by_original_claim(self, claim_id: int):
        query = select(self.model).where(self.model.original_claim_id == claim_id).order_by(self.model.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()
