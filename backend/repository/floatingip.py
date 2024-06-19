from typing import List, Optional
from uuid import UUID
from sqlalchemy import select

from backend.repository.base import BaseRepository
from backend.model.floatingip import Floatingip
from backend.schema.floatingip import FloatingipQuery


class FloatingipRepository(BaseRepository):
    async def find_floatingips_by_query(self, queryInput: Optional[FloatingipQuery]) -> List[Floatingip]:
        # 1. filter
        list_query = select(Floatingip)
        list_query = queryInput.get_filtered_query(
            query=list_query, db_model=Floatingip)
        # 2. sort
        list_query = queryInput.get_sorted_query(
            query=list_query, db_model=Floatingip)
        # 3. pagination
        list_query = queryInput.get_paginated_query(list_query)
        scalars = await self.db.scalars(list_query)

        return list(scalars.all())

    async def find_floatingip_by_id(self, id: UUID) -> Optional[Floatingip]:
        scalar = await self.db.scalar(select(Floatingip).filter(Floatingip.floatingip_id == id))
        return scalar

    async def save_floatingip(self, floatingip: Floatingip) -> Floatingip:
        self.db.add(floatingip)
        await self.db.flush()
        await self.refresh(floatingip)
        return floatingip
