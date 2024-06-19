from uuid import UUID

from backend.client.base import BaseClient
from backend.core.exception import OpenstackClientException
from backend.model.floatingip import FloatingipStatus
from backend.schema.floatingip import (FloatingipCreateRequest, FloatingipUpdateRequest, FloatingipUpdatePortRequest,
                                       FloatingipDto, FloatingipRemainLimitDto)
from backend.schema.oa_base import OpenstackBaseRequest
from backend.util.constant import OA_TOKEN_HEADER_FIELD
from backend.core.config import get_setting

SETTINGS = get_setting()


class NeutronClient(BaseClient):
    """
    openstack networking api와 관련한 클래스
    https://docs.openstack.org/api-ref/network/v2/index.html
    """

    def __init__(self) -> None:
        super().__init__(f'/networking/v2.0')

    async def create_floating_ip(self, token: str,
                                 floatingipCreateRequest: FloatingipCreateRequest) -> FloatingipDto:
        """
        - [POST] : /v2.0/floatingips
        - 201: floatingip detail
        :return : FloatingipDto
        """
        oa_request = OpenstackBaseRequest(url=f'{self.COMPONENT_URL}/floatingips', headers={
            'Content-Type': 'application/json', OA_TOKEN_HEADER_FIELD: token},
                                          data=floatingipCreateRequest.serialize())

        oa_response = await self.request_openstack(method='POST', request=oa_request,
                                                   port=SETTINGS.OPENSTACK_NEUTRON_PORT)

        return FloatingipDto.deserialize(oa_response)

    async def update_floating_ip(self, id: UUID, token: str,
                                 request: FloatingipUpdatePortRequest | FloatingipUpdateRequest) -> FloatingipDto:
        """
        - [PUT] /v2.0/floatingips/{floatingip_id}
        - 200 : floatingip detail
        :param: request: 정보 변경 dto, 혹은 port 변경 dto
        :return: FloatingipDto
        """
        oa_request = OpenstackBaseRequest(url=f'{self.COMPONENT_URL}/floatingips/{id}',
                                          headers={'Content-Type': 'application/json', OA_TOKEN_HEADER_FIELD: token},
                                          data=request.serialize())
        oa_response = await self.request_openstack(method='PUT', request=oa_request,
                                                   port=SETTINGS.OPENSTACK_NEUTRON_PORT)

        return FloatingipDto.deserialize(oa_response)

    async def delete_floating_ip(self, id: UUID, token: str) -> None:
        """
        - [DELETE] /v2.0/floatingips/{floatingip_id}
        - 204 : None
        :return: None
        """
        oa_request = OpenstackBaseRequest(url=f'{self.COMPONENT_URL}/floatingips/{id}',
                                          headers={OA_TOKEN_HEADER_FIELD: token})
        oa_response = await self.request_openstack(method='DELETE', request=oa_request,
                                                   port=SETTINGS.OPENSTACK_NEUTRON_PORT)
        return None

    async def show_floating_ip_details(self, id: UUID, token: str) -> FloatingipDto:
        """
        - [GET] /v2.0/floatingips/{floatingip_id}
        - 200 : floatingip detail
        :return: FloatingipDto
        """
        oa_request = OpenstackBaseRequest(url=f'{self.COMPONENT_URL}/floatingips/{id}',
                                          headers={OA_TOKEN_HEADER_FIELD: token})
        oa_response = await self.request_openstack(method='GET', request=oa_request,
                                                   port=SETTINGS.OPENSTACK_NEUTRON_PORT)
        return FloatingipDto.deserialize(oa_response)

    async def show_quota_details_for_tenant(self, token: str) -> FloatingipRemainLimitDto:
        """
        - [GET] /v2.0/quotas/{project_id}/details.json
        - 200 : quota detail (quota.floatingip)
        :return: FloatingipRemainLimitDto
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/quotas/{SETTINGS.OPENSTACK_PROJECT_ID}/details.json',
            headers={OA_TOKEN_HEADER_FIELD: token})
        oa_response = await self.request_openstack(method='GET', request=oa_request,
                                                   port=SETTINGS.OPENSTACK_NEUTRON_PORT)
        return FloatingipRemainLimitDto.deserialize(oa_response)
