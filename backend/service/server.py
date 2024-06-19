import asyncio
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import Depends, BackgroundTasks

from backend.client import nova_client, glance_client, cinder_client
from backend.core.exception import ApiServerException, OpenstackClientException
from backend.model.server import Server, ServerStatus
from backend.model.volume import Volume, VolumeStatus
from backend.repository.server import ServerRepository
from backend.repository.volume import VolumeRepository
from backend.schema.server import (ServerQuery, ServerCreateRequest, ServerUpdateInfoRequest,
                                   ServerPowerUpdateRequest, ServerVolumeUpdateRequest)
from backend.schema.volume import VolumeUpdateInfoRequest
from backend.util.constant import (ERR_SERVER_NOT_FOUND, ERR_FLAVOR_NOT_FOUND, ERR_IMAGE_NOT_FOUND,
                                   ERR_IMAGE_SIZE_CONFLICT, ERR_SERVER_NAME_DUPLICATED, ERR_VOLUME_NAME_DUPLICATED,
                                   ERR_SERVER_ALREADY_DELETED,
                                   ERR_VOLUME_NOT_FOUND, ERR_VOLUME_ALREADY_DELETED, ERR_SERVER_STATUS_CONFLICT,
                                   ERR_VOLUME_STATUS_CONFLICT,
                                   ERR_SERVER_VOLUME_NOT_CONNECTED, ERR_SERVER_ROOT_VOLUME_CANT_DETACH,
                                   ERR_SERVER_LIMIT_OVER, ERR_VOLUME_LIMIT_OVER)
from backend.util.func import update_model_value


class ServerService:
    def __init__(self, serverRepository: ServerRepository = Depends(), volumeRepository: VolumeRepository = Depends()):
        self.serverRepository = serverRepository
        self.volumeRepository = volumeRepository

    async def get_servers_by_query(self, queryInput: ServerQuery) -> List[Server]:
        """
        모든 server list를 반환(연관된 자원도 Overall하게 보여줘야 함)
        :return: server list
        """
        return await self.serverRepository.find_servers_by_query(queryInput)

    async def get_server_by_id(self, id: UUID) -> Server:
        """
        id(PK)로 server 조회
        :param id: 조회하려는 server의 id
        :return: server
        :raises: ApiServerException: 해당 id 존재하지 않는다면 발생
        """
        server = await self.serverRepository.find_server_by_id(id)
        if not server:
            raise ApiServerException(status=404, message=ERR_SERVER_NOT_FOUND,
                                     detail=f'server (id: {id}) not found')
        return server

    async def create_server_with_root_volume(self, serverCreateRequest: ServerCreateRequest, token: str,
                                             bg_task: BackgroundTasks) -> Server:
        """
        요청한 정보의 server와 루트볼륨을 생성
        서버 생성 완료 이후, background_tasks를 수행
        :return: server
        :raises: ApiserverException: 404(해당 flavor id 없음. 해당 image id 없음), 409(해당 name의 서버나 볼륨이 이미 존재, quota 부족, image > volume.size)
        """
        # check duplicate
        if await self.serverRepository.find_server_by_name(serverCreateRequest.name, check_alive=True):
            raise ApiServerException(status=409, message=ERR_SERVER_NAME_DUPLICATED, detail='')
        if await self.volumeRepository.find_volume_by_name(serverCreateRequest.volume.name, check_alive=True):
            raise ApiServerException(status=409, message=ERR_VOLUME_NAME_DUPLICATED, detail='')
        # check flavor
        try:
            flavorDto = await nova_client.show_flavor_details(flavor_id=serverCreateRequest.flavor_id, token=token)
        except OpenstackClientException:
            raise ApiServerException(status=404, message=ERR_FLAVOR_NOT_FOUND,
                                     detail=f'flavor (id: {serverCreateRequest.flavor_id}) not found')
        # check image
        try:
            image = await glance_client.show_image(image_id=serverCreateRequest.volume.image_id, token=token)
            size_gb = (image.virtual_size // (1024 ** 3))
            # check image virtual size ~ volume size
            if size_gb > serverCreateRequest.volume.size:
                raise ApiServerException(status=409, message=ERR_IMAGE_SIZE_CONFLICT)
        except OpenstackClientException:
            raise ApiServerException(status=404, message=ERR_IMAGE_NOT_FOUND,
                                     detail=f'image (id: {serverCreateRequest.volume.image_id}) not found')
        # [NOVA]check server quota (ram, cpu, instance)
        serverRemainLimitDto = await nova_client.show_rate_and_absolute_limits(token=token)
        if serverRemainLimitDto.remain_instances < 1 or serverRemainLimitDto.remain_cores < flavorDto.vcpus or serverRemainLimitDto.remain_rams < flavorDto.ram:
            raise ApiServerException(status=409, message=ERR_SERVER_LIMIT_OVER)
        # [CINDER] check volume quota
        volumeRemainLimitDto = await cinder_client.show_absolute_limits_for_project(token=token)
        if volumeRemainLimitDto.remain_cnt < 1 or volumeRemainLimitDto.remain_size < flavorDto.disk:
            raise ApiServerException(status=409, message=ERR_VOLUME_LIMIT_OVER)
        # 1. create server with root volume
        server_id = await nova_client.create_server(token=token, serverCreateRequest=serverCreateRequest)
        # 2. get basic info of server
        curServerDto = await nova_client.show_server_details(token=token, id=server_id)
        curServerDto.description = serverCreateRequest.description
        # 3. insert server
        new_server = await self.serverRepository.save_server(Server(**curServerDto.model_dump(exclude={'status'})))

        await self.serverRepository.commit()
        # 4. do background task
        bg_task.add_task(self._task_after_create_server, new_server, serverCreateRequest.volume.name, token)
        return new_server

    async def update_server_by_id(self, id: UUID, serverUpdateInfoRequest: ServerUpdateInfoRequest,
                                  token: str) -> Server:
        """
        해당 id의 서버의 정보를 업데이트 한다
        :raises: ApiServerException: 404(서버 없는 경우), 409 (서버 삭제된 경우, 이름 중복)
        """
        server = await self.serverRepository.find_server_by_id(id)
        # 서버가 없는 경우
        if not server:
            raise ApiServerException(status=404, message=ERR_SERVER_NOT_FOUND,
                                     detail=f'server (id: {id}) not found')
        # 서버가 삭제된 경우
        if server.deleted:
            raise ApiServerException(status=409, message=ERR_SERVER_ALREADY_DELETED, detail='')
        # 해당 이름이 이미 있는 경우
        if serverUpdateInfoRequest.name is not None and await self.serverRepository.find_server_by_name(
                serverUpdateInfoRequest.name, check_alive=True):
            raise ApiServerException(status=409, message=ERR_SERVER_NAME_DUPLICATED, detail='')
        # NOVA : 서버 정보 변경
        serverUpdateDto = await nova_client.update_server(id=id, serverUpdateInfoRequest=serverUpdateInfoRequest,
                                                          token=token)
        # db model 변경 (name, description만)
        update_model_value(server, serverUpdateDto)
        await self.serverRepository.commit()
        return server

    async def delete_server_by_id(self, id: UUID, token: str):
        """
        해당 id의 서버를 삭제한다
        ->  루트 볼륨 삭제, 추가 볼륨 연결 해제, 플로팅 IP 연결 해제, 보안그룹 연결 해제, fixed address 해제, 서버 soft delete
        : raises: ApiServerException : 404(서버 없는 경우), 409 (서버 삭제된 경우)
        """

        server = await self.serverRepository.find_server_by_id(id)
        # 서버가 없는 경우
        if not server:
            raise ApiServerException(status=404, message=ERR_SERVER_NOT_FOUND,
                                     detail=f'server (id: {id}) not found')
        # 서버가 삭제된 경우
        if server.deleted:
            raise ApiServerException(status=409, message=ERR_SERVER_ALREADY_DELETED, detail='')
        # hard delete in openstack api
        await nova_client.delete_server(id=id, token=token)
        # 성공시, db에 반영 (server soft-delete, root volume soft-delete, volume detach, floatingip detach, securitygroup detach)
        utcnow = datetime.utcnow()
        # 1. 볼륨 관련
        attached_volumes = await server.awaitable_attrs.volumes
        for attached_volume in attached_volumes:
            if attached_volume.is_root_volume:
                # 루트 볼륨 : 삭제
                attached_volume.deleted_at = utcnow
        server.volumes = [] # 모든 볼륨 연결 해제
        # 2. floatingip 연결 해제
        server.floatingip = None
        await self.serverRepository.flush() # 연관 객체 충돌 방지
        # 3. port_id 초기화
        server.fk_port_id = None
        # 3. fixed address 해제
        server.fixed_address = None
        # 4. server 삭제 처리
        server.deleted_at = utcnow
        await self.serverRepository.commit()
        return None

    async def update_server_power_by_id(self, id: UUID, serverPowerUpdateRequest: ServerPowerUpdateRequest,
                                        token: str) -> Server:
        """
        해당 id의 서버 상태를 변경한다
        :raises: ApiServerException : 404 (서버 없는 경우), 409(서버 이미 삭제된 경우, 불가능한 상태인 경우)
        """
        server = await self.serverRepository.find_server_by_id(id)
        # 서버가 없는 경우
        if not server:
            raise ApiServerException(status=404, message=ERR_SERVER_NOT_FOUND,
                                     detail=f'server (id: {id}) not found')
        # 서버가 삭제된 경우
        if server.deleted:
            raise ApiServerException(status=409, message=ERR_SERVER_ALREADY_DELETED, detail='')
        await nova_client.run_an_action(id=id, serverPowerUpdateRequest=serverPowerUpdateRequest, token=token)

        return server

    async def get_vnc_url_by_id(self, id: UUID, token: str) -> str:
        """
        vnc url을 리턴
        :return url: vnc url
        :raises: ApiServerException : 404 (서버 없는 경우), 409(서버 이미 삭제된 경우)
        """
        server = await self.serverRepository.find_server_by_id(id)
        # 서버가 없는 경우
        if not server:
            raise ApiServerException(status=404, message=ERR_SERVER_NOT_FOUND,
                                     detail=f'server (id: {id}) not found')
        # 서버가 삭제된 경우
        if server.deleted:
            raise ApiServerException(status=409, message=ERR_SERVER_ALREADY_DELETED, detail='')

        return await nova_client.create_console(id=id, token=token)

    async def attach_volume_by_id(self, id: UUID, serverVolumeUpdateRequest: ServerVolumeUpdateRequest,
                                  bg_task: BackgroundTasks,
                                  token: str) -> Server:
        """
        해당 id의 서버에 volume을 연결히고, volume의 상태를 추적하는 task를 수행
        :return: Server
        :raises: ApiServerException: 404(서버 혹은 볼륨 없는 경우), 409 (자원이 삭제된 경우, 볼륨 available 아니거나, 서버 상태 제약 )
        """
        server = await self.serverRepository.find_server_by_id(id)
        # 서버 없는 경우
        if not server:
            raise ApiServerException(status=404, message=ERR_SERVER_NOT_FOUND)
        # 서버 삭제된 경우
        if server.deleted:
            raise ApiServerException(status=409, message=ERR_SERVER_ALREADY_DELETED)

        volume = await self.volumeRepository.find_volume_by_id(id=serverVolumeUpdateRequest.volume_id)
        # 볼륨 없는 경우
        if not volume:
            raise ApiServerException(status=404, message=ERR_VOLUME_NOT_FOUND)

        # 볼륨 삭제된 경우
        if volume.deleted:
            raise ApiServerException(status=409, message=ERR_VOLUME_ALREADY_DELETED)

        # NOVA : 최신 server 정보 가져옴
        curServerDto = await nova_client.show_server_details(id=id, token=token)

        # server ACTIVE 아니라면 불가
        if curServerDto.status != ServerStatus.ACTIVE:
            raise ApiServerException(status=409, message=ERR_SERVER_STATUS_CONFLICT)

        # CINDER : 최신 volume 정보 가져옴
        curVolumeDto = await cinder_client.show_volume_detail(id=volume.volume_id, token=token)

        # volume available 아니라면 불가
        if curVolumeDto.status != VolumeStatus.AVAILABLE:
            raise ApiServerException(status=409, message=ERR_VOLUME_STATUS_CONFLICT)

        # NOVA : attach
        await nova_client.attach_volume_to_instance(id=id, serverVolumeUpdateRequest=serverVolumeUpdateRequest,
                                                    token=token)
        # TASK : 볼륨 상태 in-use 된다면 연결 처리
        bg_task.add_task(self._task_after_attach_volume, server=server, volume=volume, token=token)

        return server

    async def detach_volume_by_id(self, id: UUID, serverVolumeUpdateRequest: ServerVolumeUpdateRequest,
                                  bg_task: BackgroundTasks,
                                  token: str) -> Server:
        """
        해당 id의 서버에 volume을 해제하고, volume의 상태를 추적하는 task를 수행
        :return: Server
        :raises: ApiServerException: 404(서버 혹은 볼륨 없는 경우), 409 (자원이 삭제된 경우, 볼륨 in-use 아니거나, 서버 상태 제약, 둘이 연결되어 있지 않은 경우, 루트 볼륨인 경우)
        """
        server = await self.serverRepository.find_server_by_id(id)
        # 서버 없는 경우
        if not server:
            raise ApiServerException(status=404, message=ERR_SERVER_NOT_FOUND)
        # 서버 삭제된 경우
        if server.deleted:
            raise ApiServerException(status=409, message=ERR_SERVER_ALREADY_DELETED)

        volume = await self.volumeRepository.find_volume_by_id(id=serverVolumeUpdateRequest.volume_id)
        # 볼륨 없는 경우
        if not volume:
            raise ApiServerException(status=404, message=ERR_VOLUME_NOT_FOUND)
        # 볼륨 삭제된 경우
        if volume.deleted:
            raise ApiServerException(status=409, message=ERR_VOLUME_ALREADY_DELETED)

        # 해당 볼륨과 서버 연결되어 있지 않은 경우
        if volume.fk_server_id != id:
            raise ApiServerException(status=409, message=ERR_SERVER_VOLUME_NOT_CONNECTED)

        # 루트 볼륨인 경우
        if volume.is_root_volume:
            raise ApiServerException(status=409, message=ERR_SERVER_ROOT_VOLUME_CANT_DETACH)

        # NOVA : 최신 server 정보 가져옴
        curServerDto = await nova_client.show_server_details(id=id, token=token)

        # server ACTIVE 아니라면 불가
        if curServerDto.status != ServerStatus.ACTIVE:
            raise ApiServerException(status=409, message=ERR_SERVER_STATUS_CONFLICT)

        # CINDER : 최신 volume 정보 가져옴
        curVolumeDto = await cinder_client.show_volume_detail(id=volume.volume_id, token=token)
        # volume in-use 아니라면 불가
        if curVolumeDto.status != VolumeStatus.IN_USE:
            raise ApiServerException(status=409, message=ERR_VOLUME_STATUS_CONFLICT)

        # NOVA : detach
        await nova_client.detach_volume_to_instance(id=id, serverVolumeUpdateRequest=serverVolumeUpdateRequest,
                                                    token=token)
        # TASK : 볼륨 상태 available 된다면 해제 처리
        bg_task.add_task(self._task_after_detach_volume, volume=volume, token=token)

        return server


    async def _task_after_create_server(self,
                                        server: Server, volume_name: str, token: str,
                                        interval_time: Optional[int] = 1,
                                        polling_limit: Optional[int] = 100):
        """
        [TASK]
        check server status
        - BUILD
            do nothing
        - ACTIVE
            1. check status regularly until ACTIVE/ERROR
            2. NOVA - network interface 정보 요청 & db 수정
            3. CINDER - volume 정보로부터 루트 볼륨 여부 판단
            4. CINDER - volume row update (볼륨 이름 변경)
            5. 볼륨 정보 db 반영
        - ERROR
            1. server row(status) update
            2. return
        """
        for _ in range(polling_limit):
            await asyncio.sleep(interval_time)
            # 1. check status regularly until ACTIVE/ERROR
            curServerDto, volume_id_list = await nova_client.show_server_details_with_volume_ids(id=server.server_id,
                                                                                                 token=token)
            if curServerDto.status == ServerStatus.ACTIVE:
                # 2. NOVA - network interface 정보 요청 & db 수정
                if ((server.fk_port_id is None)
                        and (serverNetInterfaceDto := await nova_client.show_port_interface_details(id=server.server_id,
                                                                                                    token=token))):
                    server.fk_port_id = serverNetInterfaceDto.port_id
                    server.fixed_address = serverNetInterfaceDto.fixed_address
                    await self.serverRepository.save_server(server)
                    await self.serverRepository.commit()
                # 3. CINDER - volume 정보로부터 루트 볼륨 여부 판단
                for volume_id in volume_id_list:
                    volume_created = await cinder_client.show_volume_detail(id=volume_id,
                                                                            token=token)  # openstack에서 생성된 볼륨 정보
                    if volume_created.fk_image_id is not None:
                        new_volume = Volume(**volume_created.model_dump(exclude={'status'}))
                        # 4. CINDER - volume row update (볼륨 이름 변경)
                        try:
                            updatedVolumeDto = await cinder_client.update_a_volume(
                                id=new_volume.volume_id,
                                volumeUpdateInfoRequest=VolumeUpdateInfoRequest(name=volume_name),
                                token=token
                            )
                            update_model_value(db_model=new_volume, updateDto=updatedVolumeDto)  # 이름 변경 성공시 model 반영
                        except OpenstackClientException:
                            pass
                        finally:
                            # 5. 볼륨 정보 db 반영
                            await self.volumeRepository.save_volume(new_volume)
                            await self.volumeRepository.commit()
                            return
            elif curServerDto.status == ServerStatus.ERROR:
                return

    async def _task_after_attach_volume(self, server: Server, volume: Volume, token: str,
                                        interval_time: Optional[int] = 1,
                                        polling_limit: Optional[int] = 100):
        """
        [TASK]
        check volume status
        - in-use : attach 완료
        """
        for _ in range(polling_limit):
            await asyncio.sleep(interval_time)
            # CINDER : 볼륨 정보 가져와서 상태 확인
            curVolumeDto = await cinder_client.show_volume_detail(id=volume.volume_id, token=token)
            if curVolumeDto.status == VolumeStatus.IN_USE:
                # attach 완료
                volume.fk_server_id = server.server_id
                await self.volumeRepository.save_volume(volume)
                await self.volumeRepository.commit()
                return
            elif curVolumeDto.status == VolumeStatus.ERROR:
                return

    async def _task_after_detach_volume(self, volume: Volume, token: str,
                                        interval_time: Optional[int] = 1,
                                        polling_limit: Optional[int] = 100):
        """
        [TASK]
        check volume status
        - availalbe : detach 완료
        """
        for _ in range(polling_limit):
            await asyncio.sleep(interval_time)
            # CINDER : 볼륨 정보 가져와서 상태 확인
            curVolumeDto = await cinder_client.show_volume_detail(id=volume.volume_id, token=token)
            if curVolumeDto.status == VolumeStatus.AVAILABLE:
                # detach 완료
                volume.fk_server_id = None
                await self.volumeRepository.save_volume(volume)
                await self.volumeRepository.commit()
                return
            elif curVolumeDto.status == VolumeStatus.ERROR:
                return
