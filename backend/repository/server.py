from typing import List, Optional
from uuid import UUID
from sqlalchemy import select

from backend.repository.base import BaseRepository
from backend.model.server import Server
from backend.schema.server import ServerQuery


class ServerRepository(BaseRepository):
    async def find_servers_by_query(self, queryInput: Optional[ServerQuery]) -> List[Server]:
        # 1. filter
        list_query = select(Server)
        list_query = queryInput.get_filtered_query(
            query=list_query, db_model=Server)
        # 2. sort
        list_query = queryInput.get_sorted_query(
            query=list_query, db_model=Server)
        # 3. pagination
        list_query = queryInput.get_paginated_query(list_query)
        scalars = await self.db.scalars(list_query)

        return list(scalars.all())

    async def find_server_by_id(self, id: UUID, check_alive: Optional[bool] = False) -> Server:
        """
        :param check_alive: 해당 행이 유효한지(not deleted)
        """
        query = select(Server).filter(Server.server_id == id)
        if check_alive:
            query = query.filter(Server.deleted == False)
        scalar = await self.db.scalar(query)
        return scalar

    async def find_server_by_name(self, name: str, check_alive: Optional[bool] = False) -> Optional[Server]:
        query = select(Server).filter(Server.name == name)
        if check_alive:
            query = query.filter(Server.deleted_at == None)
        scalar = await self.db.scalar(query)
        return scalar

    async def find_server_by_port_id(self, port_id: UUID, check_alive: Optional[bool] = False) -> Optional[Server]:
        """
        :param check_alive: 해당 행이 유효한지(not deleted)
        """
        query = select(Server).filter(Server.fk_port_id == port_id)
        if check_alive:
            query = query.filter(Server.deleted_at == None)
        scalar = await self.db.scalar(query)
        return scalar

    async def save_server(self, server: Server) -> Server:
        self.db.add(server)
        await self.db.flush()
        await self.refresh(server)
        return server
