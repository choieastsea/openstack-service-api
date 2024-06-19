from typing import List
from uuid import UUID
from fastapi import APIRouter, status, Depends, BackgroundTasks

from backend.core.dependency import get_token_or_raise
from backend.schema.server import (ServerQuery, ServerCreateRequest, FlavorDto, ServerUpdateInfoRequest,
                                   ServerPowerUpdateRequest, ServerVolumeUpdateRequest)
from backend.schema.response import ServerResponse
from backend.service.server import ServerService

router = APIRouter(prefix="/servers", tags=["server"])


@router.get("/", response_model=List[ServerResponse], status_code=status.HTTP_200_OK)
async def get_servers(queryInput: ServerQuery = Depends(), token: str = Depends(get_token_or_raise),
                      service: ServerService = Depends()):
    """
    [API] - Get Server List
    :param token 인증 토큰
    :return: 200 - list[ServerResponse]
    :raises 401: 인증 오류
    """
    server_list = await service.get_servers_by_query(queryInput)
    return await ServerResponse.mapper(el=server_list, token=token)


@router.post("/", response_model=ServerResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_server_with_root_volume(serverCreateRequest: ServerCreateRequest,
                                         bg_task: BackgroundTasks,
                                         token: str = Depends(get_token_or_raise),
                                         service: ServerService = Depends()):
    """
    [API] - Create Server
    :param token: 인증 토큰
    :param serverCreateRequest: 사용자 입력
    :return: 202 - ServerResponse
    :raises 400: 입력 필드 조건 오류
    :raises 401: 인증 오류
    :raises 404: 해당 image/flavor 없음
    :raises 409: 서버/볼륨 이름 이미 존재, quota 부족, 볼륨 크기~이미지 크기 제약
    """
    new_server = await service.create_server_with_root_volume(serverCreateRequest=serverCreateRequest, token=token,
                                                              bg_task=bg_task)
    return await ServerResponse.mapper(el=new_server, token=token)


@router.get("/{id}/", response_model=ServerResponse, status_code=status.HTTP_200_OK)
async def get_server_by_id(id: UUID, token: str = Depends(get_token_or_raise),
                           service: ServerService = Depends()):
    """
    [API] - Get Server
    :param id: id
    :param token: 인증 토큰
    :return: 200 - list[ServerResponse]
    :raises 401: 인증 오류
    :raises 404: not found
    """
    server = await service.get_server_by_id(id)
    return await ServerResponse.mapper(el=server, token=token)


@router.patch("/{id}/", response_model=ServerResponse, status_code=status.HTTP_200_OK)
async def update_server_by_id(id: UUID, serverUpdateInfoRequest: ServerUpdateInfoRequest,
                              token: str = Depends(get_token_or_raise),
                              service: ServerService = Depends()):
    """
    [API] - Update server info (name, description)
    :param id: id
    :param token: 인증 토큰
    :return: 200 - ServerResponse
    :raises 400 : 입력 필드 오류 (name, description 255 초과)
    :raises 401: 인증 오류
    :raises 404: not found
    :raises 409 : 서버 삭제됨, 이름 unique 제약 (상태 제약은 없음)
    """
    updated_server = await service.update_server_by_id(id=id, serverUpdateInfoRequest=serverUpdateInfoRequest,
                                                       token=token)
    return await ServerResponse.mapper(el=updated_server, token=token)


@router.delete("/{id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server_by_id(id: UUID, token: str = Depends(get_token_or_raise),
                              service: ServerService = Depends()):
    """
    [API] - Delete server
    :param id: id
    :param token: 인증 토큰
    :return: 204 - No Content
    :raises 401: 인증 오류
    :raises 404: 해당하는 서버 없는 경우
    :raises 409: 이미 삭제된 경우
    """
    return await service.delete_server_by_id(id=id, token=token)


@router.post("/{id}/volumes/", status_code=status.HTTP_202_ACCEPTED)
async def attach_volume_by_id(id: UUID, serverVolumeUpdateRequest: ServerVolumeUpdateRequest,
                              bg_task: BackgroundTasks,
                              token: str = Depends(get_token_or_raise),
                              service: ServerService = Depends()):
    """
    [API] - Attach volume to server
    :param id: id
    :param token: 인증 토큰
    :param serverVolumeUpdateRequest: 사용자 입력 (volume_id)
    :return: 202 - ServerResponse
    :raises 400 : 입력 오류 (uuid)
    :raises 401 : 인증 오류
    :raises 404 : 해당 서버/볼륨 존재하지 않음
    :raises 409 : 이미 해당 볼륨은 다른 서버와 연결되어 있음 / 볼륨(available)이나 서버의 상태 제약
    """
    server = await service.attach_volume_by_id(id=id, serverVolumeUpdateRequest=serverVolumeUpdateRequest,
                                               bg_task=bg_task, token=token)
    return await ServerResponse.mapper(el=server, token=token)


@router.delete("/{id}/volumes/", status_code=status.HTTP_202_ACCEPTED)
async def detach_volume_by_id(id: UUID, serverVolumeUpdateRequest: ServerVolumeUpdateRequest,
                              bg_task: BackgroundTasks,
                              token: str = Depends(get_token_or_raise),
                              service: ServerService = Depends()):
    """
    [API] - Detach volume to server
    :param id: id
    :param token: 인증 토큰
    :param serverVolumeUpdateRequest: 사용자 입력 (volume_id)
    :return: 202 - ServerResponse
    :raises: 400: 입력 오류 (uuid)
    :raises: 401: 인증 오류
    :raises: 404: 해당 서버 존재하지 않음
    :raises: 409: 해당 볼륨이 서버와 연결되어 있지 않음 / 볼륨(in-use)이나 서버의 상태 제약
    """
    server = await service.detach_volume_by_id(id=id, serverVolumeUpdateRequest=serverVolumeUpdateRequest,
                                               bg_task=bg_task, token=token)
    return await ServerResponse.mapper(el=server, token=token)


@router.patch("/{id}/power/", status_code=status.HTTP_202_ACCEPTED)
async def update_server_power_by_id(id: UUID, serverPowerUpdateRequest: ServerPowerUpdateRequest,
                                    token: str = Depends(get_token_or_raise),
                                    service: ServerService = Depends()):
    """
    [API] - Update server's status
    :param id: id
    :param token: 인증 토큰
    :return: 202 - ServerResponse
    :raises 401: 인증 오류
    :raises 404: 해당하는 서버 없는 경우
    :raises 409: 이미 삭제된 경우, 변경이 불가능한 상태인 경우
    """
    server = await service.update_server_power_by_id(id=id, serverPowerUpdateRequest=serverPowerUpdateRequest,
                                                     token=token)
    return await ServerResponse.mapper(el=server, token=token)


@router.get("/{id}/vnc/", status_code=status.HTTP_200_OK)
async def get_vnc_url_by_id(id: UUID, token: str = Depends(get_token_or_raise), service: ServerService = Depends()):
    """
    [API] - Get server's vnc url
    :param id: id
    :param token: 인증 토큰
    :return 200 - vnc_url
    :raises: 401: 인증오류
    :raises 401: 인증 오류
    :raises 404: 해당하는 서버 없는 경우
    :raises 409: 이미 삭제된 경우
    """
    vnc_url = await service.get_vnc_url_by_id(id=id, token=token)
    return {"vnc_url": vnc_url}
