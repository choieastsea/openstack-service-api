from typing import List
from uuid import UUID
from fastapi import APIRouter, status, Depends, BackgroundTasks

from backend.core.dependency import get_token_or_raise
from backend.schema.response import VolumeResponse
from backend.schema.volume import VolumeCreateRequest, VolumeQuery, VolumeUpdateInfoRequest, VolumeSizeUpdateRequest
from backend.service.volume import VolumeService

router = APIRouter(prefix="/volumes", tags=["volume"])


@router.get("/", response_model=List[VolumeResponse], status_code=status.HTTP_200_OK)
async def get_volumes(queryInput: VolumeQuery = Depends(), token: str = Depends(get_token_or_raise),
                      service: VolumeService = Depends()):
    """
    [API] - Get Volume List
    :param token: 인증 토큰
    :param sort_by: created_at/ name
    :param order_by: asc(default)/desc
    :param page: int (default : 1)
    :param per_page: int (default : 10)
    :param volume_id: [eq/in/not]:[value]
    :param name: [eq/like]:[value]
    :return: 200 - List[VolumeResponse]
    :raises 401: 인증 오류
    """
    volume_list = await service.get_volumes_by_query(queryInput)
    return await VolumeResponse.mapper(el=volume_list, token=token)


@router.post("/", response_model=VolumeResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_volume(volumeCreateRequest: VolumeCreateRequest, token: str = Depends(get_token_or_raise),
                        service: VolumeService = Depends()):
    """
    [API] - Create Volume
    :param token: 인증 토큰
    :param volumeCreateRequest: 사용자 입력
    :return: 202 - VolumeResponse
    :raises: 400: 입력 필드 조건 오류
    :raises: 401: 인증 오류
    :raises: 409: 해당 볼륨 이름 이미 존재, limit 초과
    """
    new_volume = await service.create_volume(volumeCreateRequest=volumeCreateRequest, token=token)
    return await VolumeResponse.mapper(el=new_volume, token=token)


@router.get("/{id}/", response_model=VolumeResponse, status_code=status.HTTP_200_OK)
async def get_volume_by_id(id: UUID, token: str = Depends(get_token_or_raise),
                           service: VolumeService = Depends()):
    """
    [API] - Get Volume
    :param id: id
    :param token: 인증 토큰
    :return: 200 - VolumeResponse
    :raises 401: 인증 오류
    :raises 404: 해당하는 volume 없는 경우
    """
    volume = await service.get_volume_by_id(id=id)
    return await VolumeResponse.mapper(el=volume, token=token)


@router.patch("/{id}/", response_model=VolumeResponse, status_code=status.HTTP_200_OK)
async def update_volume_info_by_id(id: UUID, volumeUpdateInfoRequest: VolumeUpdateInfoRequest,
                                   token: str = Depends(get_token_or_raise),
                                   service: VolumeService = Depends()):
    """
    [API] - Update volume info (name, description)
    :param id: id
    :param token: 인증 토큰
    :param volumeUpdateInfoRequest: 사용자 입력 (name, description)
    :return 200 - VolumeResponse
    :raises: 400: 입력 필드 오류 (255 초과)
    :raises: 401: 인증 오류
    :raises: 404: 해당 볼륨 찾을 수 없음
    :raises: 409: 이미 볼륨 삭제됨, 이름 unique 제약
    """
    updated_volume = await service.update_volume_info_by_id(id=id, volumeUpdateInfoRequest=volumeUpdateInfoRequest,
                                                            token=token)
    return await VolumeResponse.mapper(el=updated_volume, token=token)


@router.delete("/{id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_volume_by_id(id: UUID, token: str = Depends(get_token_or_raise), service: VolumeService = Depends()):
    """
    [API] - Delete Volume
    :param id: id
    :param token: 인증 토큰
    :return: 204 - No Content
    :raises 401: 인증 오류
    :raises 404: 해당 volume 없는 경우
    :raises 409: 서버와 연결되어 있는 경우, 삭제 불가능한 상태인 경우
    """
    return await service.delete_volume_by_id(id=id, token=token)


@router.patch("/{id}/size/", response_model=VolumeResponse, status_code=status.HTTP_202_ACCEPTED)
async def extend_volume_size_by_id(id: UUID, volumeSizeUpdateRequest: VolumeSizeUpdateRequest, bg_task: BackgroundTasks,
                                   token: str = Depends(get_token_or_raise), service: VolumeService = Depends()):
    """
    [API] - Upgrade Volume Size
    :param id: id
    :param token: 인증토큰
    :return 202 - VolumeResponse
    :raises 400: 입력 오류 (2 이하)
    :raises 401: 인증 오류
    :raises 404: 해당 volume 없는 경우
    :raises 409: 현재보다 작거나 같은 크기로 변경하는 경우, 볼륨 상태가 available 아닌 경우, quota 부족한 경우
    """
    volume = await service.extend_volume_size_by_id(id=id, token=token, volumeSizeUpdateRequest=volumeSizeUpdateRequest,
                                                    bg_task=bg_task)
    return await VolumeResponse.mapper(el=volume, token=token)
