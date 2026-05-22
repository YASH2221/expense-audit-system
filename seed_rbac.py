import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import AsyncSessionLocal, engine
from app.models.user import User
from app.models.enums import UserRole
from app.db.base import Base

async def seed():
    async def add_user(name, email, role):
        async with AsyncSessionLocal() as session:
            try:
                from sqlalchemy import select
                res = await session.execute(select(User).where(User.email == email))
                if not res.scalars().first():
                    u = User(name=name, email=email, role=role)
                    session.add(u)
                    await session.commit()
                    print(f"Committed {name}")
                else:
                    print(f"{name} already exists")
            except Exception as e:
                print(f"Error adding {name}: {e}")

    await add_user("Employee One", "emp1@company.com", UserRole.EMPLOYEE)
    await add_user("Reviewer One", "rev1@company.com", UserRole.REVIEWER)
    await add_user("Controller One", "ctl1@company.com", UserRole.CONTROLLER)
    print("Seeding process finished.")

if __name__ == "__main__":
    asyncio.run(seed())
