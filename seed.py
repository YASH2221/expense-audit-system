import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models.user import User
from app.models.enums import Role

async def seed():
    async with AsyncSessionLocal() as session:
        # Check if user exists
        query = select(User).where(User.id == 1)
        result = await session.execute(query)
        user = result.scalars().first()
        
        if not user:
            user = User(
                id=1,
                name="Test Employee",
                email="employee@example.com",
                role=Role.EMPLOYEE
            )
            session.add(user)
            await session.commit()
            print("Seeded User ID: 1")
        else:
            print("User ID: 1 already exists")

if __name__ == "__main__":
    asyncio.run(seed())
