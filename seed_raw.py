import asyncio
from app.db.database import engine
# pyrefly: ignore [missing-import]
from sqlalchemy import text

async def seed_raw():
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO users (name, email, role) 
            VALUES 
                ('Reviewer One', 'rev1@company.com', 'REVIEWER'),
                ('Controller One', 'ctl1@company.com', 'CONTROLLER')
            ON CONFLICT (email) DO NOTHING
        """))
        print("Raw seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed_raw())
