from uuid import UUID

from backend.client.base import BaseClient
from backend.core.config import get_setting
from backend.schema.oa_base import OpenstackBaseRequest
from backend.schema.volume import VolumeCreateRequest, VolumeDto, VolumeUpdateInfoRequest, VolumeSizeUpdateRequest, \
    VolumeRemainLimitDto
from backend.util.constant import OA_TOKEN_HEADER_FIELD

SETTINGS = get_setting()


class CinderClient(BaseClient):
    """
    openstack volume api와 관련한 클래스
    https://docs.openstack.org/api-ref/block-storage/v3/index.html
    """

    def __init__(self) -> None:
        super().__init__(f'/volume/v3/{SETTINGS.OPENSTACK_PROJECT_ID}')

    async def create_volume(self, token: str, volumeCreateRequest: VolumeCreateRequest) -> VolumeDto:
        """
        - [POST] : /v3/{project_id}/volumes

        - 202 : volume detail (creating -> available)

        :return: VolumeDto
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/volumes',
            headers={'Content-Type': 'application/json', OA_TOKEN_HEADER_FIELD: token},
            data=volumeCreateRequest.serialize()
        )
        oa_response = await self.request_openstack('POST', oa_request)
        return VolumeDto.deserialize(oa_response)

    async def show_volume_detail(self, id: UUID, token: str) -> VolumeDto:
        """
        - [GET] : /v3/{project_id}/volumes/{volume_id}

        - 200 : volume detail

        :return: VolumeDto
        """
        oa_request = OpenstackBaseRequest(url=f'{self.COMPONENT_URL}/volumes/{id}', headers={
            OA_TOKEN_HEADER_FIELD: token})
        oa_response = await self.request_openstack('GET', oa_request)

        return VolumeDto.deserialize(oa_response)

    async def update_a_volume(self, id: UUID, token: str,
                              volumeUpdateInfoRequest: VolumeUpdateInfoRequest) -> VolumeDto:
        """
        - [PUT] : /v3/{project_id}/volumes/{volume_id}

        - 200 : volume detail

        :return: VolumeDto
        """
        oa_request = OpenstackBaseRequest(url=f'{self.COMPONENT_URL}/volumes/{id}',
                                          headers={'Content-Type': 'application/json', OA_TOKEN_HEADER_FIELD: token},
                                          data=volumeUpdateInfoRequest.serialize())
        oa_response = await self.request_openstack('PUT', oa_request)
        return VolumeDto.deserialize(oa_response)

    async def show_absolute_limits_for_project(self, token: str) -> VolumeRemainLimitDto:
        """
        - [PUT] : /v3/{project_id}/limits

        - 200 : limits (maxTotalVolumeGigabytes, totalGigabytesUsed / maxTotalVolumes, totalGigabytesUsed)

        :return: VolumeRemainLimitDto
        """
        oa_request = OpenstackBaseRequest(url=f'{self.COMPONENT_URL}/limits',
                                          headers={'Content-Type': 'application/json', OA_TOKEN_HEADER_FIELD: token},
                                          )
        oa_response = await self.request_openstack('GET', oa_request)
        return VolumeRemainLimitDto.deserialize(oa_response)

    async def delete_a_volume(self, id: UUID, token: str) -> None:
        """
        - [DELETE] : /v3/{project_id}/volumes/{volume_id}

        - 202 : null ( deleting -> X / error_deleting)

        :return: None
        """
        oa_request = OpenstackBaseRequest(url=f'{self.COMPONENT_URL}/volumes/{id}',
                                          headers={OA_TOKEN_HEADER_FIELD: token})
        oa_response = await self.request_openstack('DELETE', oa_request)
        return None

    async def extend_a_volume_size(self, id: UUID, token: str,
                                   volumeSizeUpdateRequest: VolumeSizeUpdateRequest) -> None:
        """
        - [POST] : /v3/{project_id}/volumes/{volume_id}/action

        - 202 : null ( extending -> error_extending)

        :return: None
        """
        oa_request = OpenstackBaseRequest(url=f'{self.COMPONENT_URL}/volumes/{id}/action',
                                          headers={'Content-Type': 'application/json', OA_TOKEN_HEADER_FIELD: token},
                                          data=volumeSizeUpdateRequest.serialize())
        oa_response = await self.request_openstack('POST', oa_request)
        return None
