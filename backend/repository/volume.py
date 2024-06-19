from typing import Optional, List
from uuid import UUID
from sqlalchemy import select

from backend.model.volume import Volume
from backend.repository.base import BaseRepository
from backend.schema.volume import VolumeQuery


class VolumeRepository(BaseRepository):
    async def save_volume(self, volume: Volume) -> Volume:
        """
        volume 객체를 DB에 저장
        - 이미 session에 올라가 있는 경우 : update
        - session에 올라가 있지 않은 경우 : insert
        :return: volume: DB에 반영된 볼륨 객체
        """
        self.db.add(volume)
        await self.db.flush()
        await self.refresh(volume)
        return volume

    async def find_volumes_by_query(self, queryInput: Optional[VolumeQuery]) -> List[Volume]:
        """
        해당 query에 해당하는 volume list를 select
        """
        # 1. filter
        list_query = select(Volume)
        list_query = queryInput.get_filtered_query(
            query=list_query, db_model=Volume
        )
        # 2. sort
        list_query = queryInput.get_sorted_query(
            query=list_query, db_model=Volume
        )
        # 3. pagination
        list_query = queryInput.get_paginated_query(list_query)
        scalars = await self.db.scalars(list_query)

        return list(scalars.all())

    async def find_volume_by_id(self, id: UUID, check_alive: Optional[bool] = False) -> Optional[Volume]:
        """
        해당 id(PK)를 갖는 volume 반환
        :param id: PK
        :param check_alive: (optional) delete 된 볼륨도 찾을지 여부
        :return: Optional[Volume]
        """
        query = select(Volume).filter(Volume.volume_id == id)
        if check_alive:
            query = query.filter(Volume.deleted_at == None)
        scalar = await self.db.scalar(query)
        return scalar

    async def find_volume_by_name(self, name: str, check_alive: Optional[bool] = False) -> Optional[Volume]:
        """
        해당 name(str)를 갖는 volume 반환
        :param name: 볼륨명
        :param check_alive: (optional) delete 된 볼륨도 찾을지 여부
        :return: Optional[Volume]
        """
        query = select(Volume).filter(Volume.name == name)
        if check_alive:
            query = query.filter(Volume.deleted_at == None)
        scalar = await self.db.scalar(query)
        return scalar
