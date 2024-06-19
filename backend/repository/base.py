from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.db import db


class BaseRepository:
    def __init__(self, session: AsyncSession = Depends(db.get_db)):
        self.db = session

    async def commit(self):
        await self.db.commit()

    async def rollback(self):
        await self.db.rollback()

    async def refresh(self, *args, **kwargs):
        await self.db.refresh(*args, **kwargs)

    async def flush(self):
        await self.db.flush()
