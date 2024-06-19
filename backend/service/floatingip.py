from datetime import datetime
from typing import List
from fastapi import Depends, BackgroundTasks
from uuid import UUID

from backend.client import neutron_client, nova_client
from backend.core.exception import ApiServerException
from backend.model.server import ServerStatus
from backend.model.floatingip import Floatingip
from backend.repository.floatingip import FloatingipRepository
from backend.repository.server import ServerRepository
from backend.schema.floatingip import (FloatingipCreateRequest, FloatingipUpdateRequest, FloatingipUpdatePortRequest,
                                       FloatingipQuery)
from backend.util.constant import (ERR_FLOATINGIP_NOT_FOUND, ERR_FLOATINGIP_STATUS_CONFLICT,
                                   ERR_FLOATINGIP_PORT_CONFLICT, ERR_SERVER_PORT_NOT_FOUND, ERR_SERVER_STATUS_CONFLICT,
                                   ERR_FLOATINGIP_LIMIT_OVER)
from backend.util.func import update_model_value


class FloatingipService:
    def __init__(self, floatingipRepository: FloatingipRepository = Depends(),
                 serverRepository: ServerRepository = Depends()):
        self.floatingipRepository = floatingipRepository
        self.serverRepository = serverRepository

    async def get_floatingips_by_query(self, queryInput: FloatingipQuery) -> List[Floatingip]:
        """
        모든 floatingip list를 반환
        :return: floatingip list
        """
        return await self.floatingipRepository.find_floatingips_by_query(queryInput)

    async def get_floatingip_by_id(self, id: UUID) -> Floatingip:
        """
        id(PK)로 floatingip 조회
        :param id: 조회하려는 floatingip의 id
        :return: floatingip 객체
        :raises ApiServerException: 404(해당 id 존재하지 않음)
        """
        floatingip = await self.floatingipRepository.find_floatingip_by_id(id)
        if not floatingip:
            raise ApiServerException(status=404, message=ERR_FLOATINGIP_NOT_FOUND,
                                     detail=f'floatingip (id :{id}) not found')
        return floatingip

    async def create_floatingip(self, token, floatingipCreateRequest: FloatingipCreateRequest) -> Floatingip:
        """
        neutron client 이용하여 floatingip 객체 생성
        :param token: 인증 토큰
        :param floatingipCreateRequest: 사용자 입력 값
        :return: floatingip 객체
        :raises: ApiServerException: 409 (quota 부족)
        """
        # 1. check floatingip quota
        floatingipRemainLimitDto = await neutron_client.show_quota_details_for_tenant(token=token)
        if floatingipRemainLimitDto.remain_cnt <= 0:
            raise ApiServerException(status=409, message=ERR_FLOATINGIP_LIMIT_OVER)
        # 2. create in openstack api
        floatingipDto = await neutron_client.create_floating_ip(token, floatingipCreateRequest)
        # 3. create in db
        floatingip = Floatingip(**floatingipDto.model_dump(exclude={'status'}))
        new_floatingip = await self.floatingipRepository.save_floatingip(floatingip)
        await self.floatingipRepository.commit()
        return new_floatingip

    async def update_floatingip_by_id(self, id: UUID, token: str,
                                      floatingipUpdateRequest: FloatingipUpdateRequest) -> Floatingip:
        """
        neutron client 이용하여 floatingip 수정
        :param token: 인증 토큰
        :param floatingipUpdateRequest: 사용자 입력값
        :return: floatingip 객체
        :raises ApiServerException: 404(해당 floating ip 없음), 409(해당 floatingip 삭제됨)
        """
        # 1. find floatingip by id
        floatingip = await self.floatingipRepository.find_floatingip_by_id(id)
        if not floatingip:
            raise ApiServerException(status=404, message=ERR_FLOATINGIP_NOT_FOUND,
                                     detail=f'floatingip (id :{id}) not found')
        if floatingip.deleted:
            raise ApiServerException(status=409, message=ERR_FLOATINGIP_STATUS_CONFLICT)
        # 2. update in openstack client
        floatingipDto = await neutron_client.update_floating_ip(floatingip.floatingip_id, token,
                                                                floatingipUpdateRequest)
        # 3. update in db
        update_model_value(db_model=floatingip, updateDto=floatingipDto)
        await self.floatingipRepository.commit()
        return floatingip

    async def delete_floatingip_by_id(self, id: UUID, token: str) -> None:
        """
        neutron client 이용하여 floatingip 삭제
        :param id: floatingip id
        :param token: 인증 토큰
        :return: None
        :raises ApiServerException: 404(해당 floating ip 없음), 409(해당 floatingip 삭제됨 / 이미 서버와 연결되어 있음)
        """
        # 1. find floatingip by id
        floatingip = await self.floatingipRepository.find_floatingip_by_id(id)
        if not floatingip:
            raise ApiServerException(status=404, message=ERR_FLOATINGIP_NOT_FOUND,
                                     detail=f'floatingip (id :{id}) not found')
        if floatingip.deleted:
            raise ApiServerException(status=409, message=ERR_FLOATINGIP_STATUS_CONFLICT)
        if floatingip.fk_port_id:
            raise ApiServerException(status=409, message=ERR_FLOATINGIP_PORT_CONFLICT)
        # 2. hard delete in openstack api
        await neutron_client.delete_floating_ip(floatingip.floatingip_id, token)
        # 3. soft delete in db (update deleted_at)
        floatingip.deleted_at = datetime.utcnow()
        await self.floatingipRepository.commit()
        return None

    async def update_port_by_floatingip_id(self, id: UUID, token: str,
                                           floatingipUpdatePortRequest: FloatingipUpdatePortRequest,
                                           bg_task: BackgroundTasks) -> Floatingip:
        """
        neutron client 이용하여 floatingip와 port 연결/해제
        :param id: floatingip id
        :param token: 인증 토큰
        :param floatingipUpdatePortRequest: 사용자 입력 (port_id)
        :param bg_task: background task 객체
        :return: 수정(연결/해제)된 floatingip 객체 & task 수행
        :raises ApiServerException: 404(해당 floating ip 없음, 해당 port id의 서버 없음)/ 409(해당 floating ip 이미 삭제, 해당 서버 상태가 ACTIVE가 아님)
        """
        # 1. find floatingip by id
        floatingip = await self.floatingipRepository.find_floatingip_by_id(id)
        if not floatingip:
            raise ApiServerException(status=404, message=ERR_FLOATINGIP_NOT_FOUND,
                                     detail=f'floatingip (id :{id}) not found')
        if floatingip.deleted:
            raise ApiServerException(status=409, message=ERR_FLOATINGIP_STATUS_CONFLICT)

        # 2. find server by port id
        if floatingipUpdatePortRequest.port_id:
            server = await self.serverRepository.find_server_by_port_id(floatingipUpdatePortRequest.port_id)
            if not server:
                raise ApiServerException(status=404, message=ERR_SERVER_PORT_NOT_FOUND,
                                         detail=f'server with port (id: {floatingipUpdatePortRequest.port_id}) not found')
            curServerDto = await nova_client.show_server_details(id=server.server_id, token=token)
            if curServerDto.status != ServerStatus.ACTIVE:
                raise ApiServerException(status=409, message=ERR_SERVER_STATUS_CONFLICT,
                                         detail=f'current server status : {curServerDto.status.value}')
        # 3. update in openstack api
        floatingipDto = await neutron_client.update_floating_ip(id, token, floatingipUpdatePortRequest)
        # 4. update in db
        if not floatingipDto.fk_port_id:
            # port_id None이라면 연결 해제 의미함
            floatingip.fk_port_id = None
        update_model_value(floatingip, floatingipDto)
        await self.floatingipRepository.commit()
        return floatingip
