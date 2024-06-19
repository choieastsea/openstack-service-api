from fastapi import APIRouter, Depends, status, BackgroundTasks
from uuid import UUID

from backend.core.dependency import get_token_or_raise
from backend.schema.floatingip import (FloatingipCreateRequest, FloatingipUpdateRequest,
                                       FloatingipUpdatePortRequest, FloatingipQuery)
from backend.schema.response import FloatingipResponse
from backend.service.floatingip import FloatingipService

router = APIRouter(prefix="/floatingips", tags=["floatingip"])


@router.get("/", response_model=list[FloatingipResponse], status_code=status.HTTP_200_OK)
async def get_floatingips(queryInput: FloatingipQuery = Depends(), token: str = Depends(get_token_or_raise),
                          service: FloatingipService = Depends()):
    """
    [API] - Get Floatingip List
    :param token: 인증 토큰
    :return: 200 - list[FloatingipResponse]
    :raises 401: 인증 오류
    """
    floatingip_list = await service.get_floatingips_by_query(queryInput)
    return await FloatingipResponse.mapper(el=floatingip_list, token=token)


@router.post("/", response_model=FloatingipResponse, status_code=status.HTTP_201_CREATED)
async def create_floatingip(floatingipCreateRequest: FloatingipCreateRequest, token: str = Depends(get_token_or_raise),
                            service: FloatingipService = Depends()):
    """
    [API] - Create Floatingip
    :param token: 인증 토큰
    :param floatingipCreateRequest: 사용자 입력
    :return: 201 - FloatingipResponse
    :raises 400: 입력 필드 조건 오류
    :raises 401: 인증 오류
    :raises 409: 할당 받을 수 있는 ip가 없는 경우(quota 부족)
    """
    new_floatingip = await service.create_floatingip(token, floatingipCreateRequest)
    return await FloatingipResponse.mapper(el=new_floatingip, token=token)


@router.get("/{floatingip_id}/", response_model=FloatingipResponse, status_code=status.HTTP_200_OK)
async def get_floatingip_by_id(floatingip_id: UUID, token: str = Depends(get_token_or_raise),
                               service: FloatingipService = Depends()):
    """
    [API] - Get Floatingip
    :param floatingip_id: id
    :param token: 인증 토큰
    :return: 200 - FloatingipResponse
    :raises 401: 인증 오류
    :raises 404: 해당하는 floatingip 없는 경우
    """
    floatingip = await service.get_floatingip_by_id(floatingip_id)
    return await FloatingipResponse.mapper(el=floatingip, token=token)


@router.patch("/{floatingip_id}/", response_model=FloatingipResponse, status_code=status.HTTP_200_OK)
async def update_floatingip_by_id(floatingip_id: UUID, floatingipUpdateRequest: FloatingipUpdateRequest,
                                  token: str = Depends(get_token_or_raise),
                                  service: FloatingipService = Depends()):
    """
    [API] - Update Floatingip
    :param floatingip_id: id
    :param token: 인증 토큰
    :return: 200 - FloatingipResponse
    :raises 401: 인증 오류
    :raises 404: 해당하는 floatingip 없는 경우
    """
    modified_floatingip = await service.update_floatingip_by_id(floatingip_id, token, floatingipUpdateRequest)
    return await FloatingipResponse.mapper(el=modified_floatingip, token=token)


@router.delete("/{floatingip_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_floatingip_by_id(floatingip_id: UUID, token: str = Depends(get_token_or_raise),
                                  service: FloatingipService = Depends()):
    """
    [API] - Delete Floatingip
    :param floatingip_id: id
    :param token: 인증 토큰
    :return: 204 - No Content
    :raises 401: 인증 오류
    :raises 404: 해당하는 floatingip 없는 경우
    :rasies 409: 서버와 연결되어 있는 경우
    """
    return await service.delete_floatingip_by_id(floatingip_id, token)


@router.patch("/{floatingip_id}/ports/", response_model=FloatingipResponse,
              status_code=status.HTTP_202_ACCEPTED)
async def update_port_by_floatingip_id(floatingip_id: UUID,
                                       floatingipUpdatePortRequest: FloatingipUpdatePortRequest,
                                       bg_task: BackgroundTasks,
                                       token: str = Depends(get_token_or_raise),
                                       service: FloatingipService = Depends()
                                       ):
    """
    [API] - Attach or Detach floatingip to port(server)
    :param floatingip_id: id
    :param token: 인증 토큰
    :return: 202 - FloatingipResponse
    :raises 404: 해당하는 floatingip 없는 경우, 해당하는 port id 없는 경우
    :raises 409: 해당 floatingip 불가능한 상태인 경우, 해당 서버 불가능한 경우
    """
    modified_floatingip = await service.update_port_by_floatingip_id(floatingip_id,
                                                                     token,
                                                                     floatingipUpdatePortRequest,
                                                                     bg_task)
    return await FloatingipResponse.mapper(el=modified_floatingip, token=token)
