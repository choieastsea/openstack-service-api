import asyncio
from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import Depends, BackgroundTasks

from backend.client import cinder_client
from backend.core.exception import ApiServerException
from backend.model.volume import Volume, VolumeStatus
from backend.repository.volume import VolumeRepository
from backend.schema.volume import VolumeCreateRequest, VolumeQuery, VolumeUpdateInfoRequest, VolumeSizeUpdateRequest
from backend.util.constant import (ERR_VOLUME_LIMIT_OVER, ERR_VOLUME_NOT_FOUND,
                                   ERR_VOLUME_ALREADY_DELETED, ERR_VOLUME_NAME_DUPLICATED, ERR_VOLUME_SERVER_CONFLICT,
                                   ERR_VOLUME_STATUS_CONFLICT, ERR_VOLUME_SIZE_UPGRADE_CONFLICT)
from backend.util.func import update_model_value


class VolumeService:
    def __init__(self, volumeRepository: VolumeRepository = Depends()):
        self.volumeRepository = volumeRepository

    async def get_volumes_by_query(self, queryInput: VolumeQuery):
        """
        모든 volume list를 반환
        :return: volume list
        """
        return await self.volumeRepository.find_volumes_by_query(queryInput)

    async def get_volume_by_id(self, id: UUID):
        """
        id(PK)로 volume 조회
        :param id: 조회하려는 volume의 id
        :return: volume
        :raises ApiServerException: 404(해당 볼륨 없음)
        """
        volume = await self.volumeRepository.find_volume_by_id(id=id)
        if not volume:
            raise ApiServerException(status=404, message=ERR_VOLUME_NOT_FOUND, detail=f'volume (id : {id}) not found')
        return volume

    async def create_volume(self, volumeCreateRequest: VolumeCreateRequest, token: str) -> Volume:
        """
        요청한 정보의 볼륨을 생성
        :return : volume
        :raises : ApiServerException: 409 (용량 부족한 경우, 해당 이름 이미 있는 경우)
        """
        # 삭제되지 않은 볼륨 중 해당 이름이 이미 있는 경우
        if await self.volumeRepository.find_volume_by_name(name=volumeCreateRequest.name, check_alive=True):
            raise ApiServerException(status=409, message=ERR_VOLUME_NAME_DUPLICATED, detail='')
        # 남은 용량 확인
        volumeRemainLimitDto = await cinder_client.show_absolute_limits_for_project(token=token)
        if volumeRemainLimitDto.remain_cnt <= 0 or volumeRemainLimitDto.remain_size < volumeCreateRequest.size:
            raise ApiServerException(status=409, error_type='error', message=ERR_VOLUME_LIMIT_OVER)
        volumeDto = await cinder_client.create_volume(volumeCreateRequest=volumeCreateRequest, token=token)
        new_volume = await self.volumeRepository.save_volume(Volume(**volumeDto.model_dump(exclude={'status'})))
        await self.volumeRepository.commit()
        return new_volume

    async def update_volume_info_by_id(self, id: UUID, volumeUpdateInfoRequest: VolumeUpdateInfoRequest, token: str):
        """
        해당 id의 볼륨 정보를 업데이트 한다
        :return: updated volume
        :raises: ApiServerException: 404(볼륨 없는 경우), 409(볼륨 삭제된 경우, 이름 중복)
        """
        volume = await self.volumeRepository.find_volume_by_id(id=id)
        # 볼륨 없는 경우
        if not volume:
            raise ApiServerException(status=404, message=ERR_VOLUME_NOT_FOUND, detail=f'volume (id : {id}) not found')
        # 볼륨 삭제된 경우
        if volume.deleted:
            raise ApiServerException(status=409, message=ERR_VOLUME_ALREADY_DELETED, detail='')
        # 삭제되지 않은 볼륨 중 해당 이름이 이미 있는 경우
        if (volumeUpdateInfoRequest.name is not None
                and await self.volumeRepository.find_volume_by_name(name=volumeUpdateInfoRequest.name,
                                                                    check_alive=True)):
            raise ApiServerException(status=409, message=ERR_VOLUME_NAME_DUPLICATED, detail='')
        # CINDER : 볼륨 정보 변경 요청
        volumeDto = await cinder_client.update_a_volume(id=id, token=token,
                                                        volumeUpdateInfoRequest=volumeUpdateInfoRequest)
        # DB model 변경
        update_model_value(volume, volumeDto)
        await self.volumeRepository.commit()
        return volume

    async def delete_volume_by_id(self, id: UUID, token: str) -> None:
        """
        cinder client 이용하여 volume 삭제
        :param id: volume id
        :param token: 인증 토큰
        :return: None
        :raises: ApiServerException: 404(해당 volume 없음) / 409(해당 volume 이미 삭제됨 , 서버와 연결되어 있음 , 볼륨 삭제 불가능한 상태)
        """
        volume = await self.volumeRepository.find_volume_by_id(id=id)
        # 볼륨 없는 경우
        if not volume:
            raise ApiServerException(status=404, message=ERR_VOLUME_NOT_FOUND, detail=f'volume (id : {id}) not found')
        # 볼륨 삭제된 경우
        if volume.deleted:
            raise ApiServerException(status=409, message=ERR_VOLUME_ALREADY_DELETED)
        # 서버와 이미 연결되어 있는 경우
        if volume.fk_server_id:
            raise ApiServerException(status=409, message=ERR_VOLUME_SERVER_CONFLICT,
                                     detail=f'server id: {volume.fk_server_id}')
        # CINDER : 볼륨 상태 확인: available, in-use, error, error_restoring, error_extending 상태면 삭제 가능
        curVolumeDto = await cinder_client.show_volume_detail(id=id, token=token)
        cur_status = curVolumeDto.status
        if cur_status not in (
                VolumeStatus.AVAILABLE, VolumeStatus.IN_USE, VolumeStatus.ERROR, VolumeStatus.ERROR_RESTORING,
                VolumeStatus.ERROR_EXTENDING):
            raise ApiServerException(status=409, message=ERR_VOLUME_STATUS_CONFLICT)
        # CINDER : 볼륨 삭제 요청
        await cinder_client.delete_a_volume(id=id, token=token)
        # DB soft delete
        volume.deleted_at = datetime.utcnow()
        await self.volumeRepository.commit()
        return None

    async def extend_volume_size_by_id(self, id: UUID, volumeSizeUpdateRequest: VolumeSizeUpdateRequest, token: str,
                                       bg_task: BackgroundTasks):
        """
        cinder client 이용하여 볼륨 용량 증가 요청 + polling하며 용량 증가되었다면 업데이트
        :param id: volume id
        :param token: 인증 토큰
        :return: None
        :raises: ApiServerException: 404(해당 volume 없음) / 409(해당 volume 이미 삭제됨 , 볼륨 상태 availalbe 아닌 경우 ,  현재보다 작거나 같은 크기로 변경하는 경우, quota 부족한 경우)
        """
        volume = await self.volumeRepository.find_volume_by_id(id=id)
        # 볼륨 없는 경우
        if not volume:
            raise ApiServerException(status=404, message=ERR_VOLUME_NOT_FOUND, detail=f'volume (id : {id}) not found')
        # 볼륨 삭제된 경우
        if volume.deleted:
            raise ApiServerException(status=409, message=ERR_VOLUME_ALREADY_DELETED)
        # CINDER : 볼륨 정보 GET
        curVolumeDto = await cinder_client.show_volume_detail(id=id, token=token)
        # 볼륨 상태 available 여야함
        if curVolumeDto.status != VolumeStatus.AVAILABLE:
            raise ApiServerException(status=409, message=ERR_VOLUME_STATUS_CONFLICT)
        # 현재보다 작거나 같은 크기로 변경하려는 경우
        if curVolumeDto.size >= volumeSizeUpdateRequest.new_size:
            raise ApiServerException(status=409, message=ERR_VOLUME_SIZE_UPGRADE_CONFLICT,
                                     detail=f'current volume size : {curVolumeDto.size}GB')
        # CINDER : quota 부족한 경우
        volumeRemainLimitDto = await cinder_client.show_absolute_limits_for_project(token=token)
        if volumeRemainLimitDto.remain_size < (volumeSizeUpdateRequest.new_size - curVolumeDto.size):
            raise ApiServerException(status=409, message=ERR_VOLUME_LIMIT_OVER)
        # CINDER : 볼륨 용량 증가 요청
        await cinder_client.extend_a_volume_size(id=id, volumeSizeUpdateRequest=volumeSizeUpdateRequest, token=token)
        # task
        bg_task.add_task(self._task_after_extend_volume, token, volume)
        return volume

    async def _task_after_extend_volume(self, token: str, volume: Volume,
                                        interval_time: Optional[int] = 1,
                                        polling_limit: Optional[int] = 100):
        """
        check volume status & set size
        - EXTENDING
        - AVAILABLE : db volume size update
        - ERROR_EXTENDING
        """
        for _ in range(polling_limit):
            await asyncio.sleep(interval_time)
            # CINDER check info regularly until AVAILABLE/ERROR_EXTENDING
            volumeDto = await cinder_client.show_volume_detail(id=volume.volume_id, token=token)
            if volumeDto.status == VolumeStatus.AVAILABLE:
                # DB volume update
                volume.size = volumeDto.size
                await self.volumeRepository.save_volume(volume)
                await self.volumeRepository.commit()
                return
            elif volumeDto.status == VolumeStatus.ERROR_EXTENDING:
                return
