import json
from typing import List, Tuple, Optional
from uuid import UUID

from backend.client.base import BaseClient
from backend.core.exception import OpenstackClientException
from backend.model.server import ServerStatus
from backend.schema.oa_base import OpenstackBaseRequest
from backend.schema.server import (ServerDto, ServerCreateRequest, FlavorDto, ServerNetInterfaceDto,
                                   ServerUpdateInfoRequest, ServerUpdateDto, ServerPowerUpdateRequest,
                                   ServerVolumeUpdateRequest, ServerRemainLimitDto)
from backend.util.constant import OA_TOKEN_HEADER_FIELD


class NovaClient(BaseClient):
    """
    openstack compute api와 관련한 클래스
    https://docs.openstack.org/api-ref/compute/
    """

    def __init__(self) -> None:
        super().__init__(f'/compute/v2.1')

    async def create_server(self, token: str,
                            serverCreateRequest: ServerCreateRequest) -> UUID:
        """
        - [POST] : /servers (v2.95)
        - 202 : server_id를 포함한 간단한 정보 (BUILDING -> ACTIVE)
        :return: UUID (server_id)
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/servers',
            headers={'Content-Type': 'application/json', OA_TOKEN_HEADER_FIELD: token,
                     'X-OpenStack-Nova-API-Version': '2.95'},
            data=serverCreateRequest.serialize()
        )
        oa_response = await self.request_openstack(method='POST', request=oa_request)
        return UUID(oa_response.model_dump()['data']['server']['id'])

    async def show_server_details(self, id: UUID, token: str) -> ServerDto:
        """
        - [GET] : /servers/{server_id}
        - 200 : server detail
        :return: ServerDto
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/servers/{id}',
            headers={OA_TOKEN_HEADER_FIELD: token}
        )
        oa_response = await self.request_openstack(method='GET', request=oa_request)
        return ServerDto.deserialize(oa_response)

    async def show_server_details_with_volume_ids(self, id: UUID, token: str) -> Tuple[ServerDto, List[UUID]]:
        """
        - [GET] : /servers/{server_id}
        - 200 : server detail
        :return: ServerDto, List[UUID] (연결된 volume id list)
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/servers/{id}',
            headers={OA_TOKEN_HEADER_FIELD: token}
        )
        oa_response = await self.request_openstack(method='GET', request=oa_request)
        return ServerDto.deserialize(oa_response), ServerDto.deserialize_volumes(oa_response)

    async def show_port_interface_details(self, id: UUID, token: str) -> ServerNetInterfaceDto:
        """
        - [GET] - /servers/{server_id}/os-interface
        - 200 : interfaceAttachments (network_id, port_id, fixed_ip_address)
        :return: ServerNetInterfaceDto (port_id, fixed_address)
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/servers/{id}/os-interface',
            headers={OA_TOKEN_HEADER_FIELD: token}
        )
        oa_response = await self.request_openstack(method='GET', request=oa_request)
        return ServerNetInterfaceDto.deserialize(oa_response)

    async def update_server(self, id: str, serverUpdateInfoRequest: ServerUpdateInfoRequest,
                            token: str) -> ServerUpdateDto:
        """
        - [PUT] - /servers/{server_id} (v 2.95)
        - 200 : server detail
        :return: ServerUpdateDto (name, description)
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/servers/{id}',
            headers={'Content-Type': 'application/json', OA_TOKEN_HEADER_FIELD: token,
                     'X-OpenStack-Nova-API-Version': '2.95'},
            data=serverUpdateInfoRequest.serialize()
        )
        oa_response = await self.request_openstack(method='PUT', request=oa_request)
        return ServerUpdateDto.deserialize(oa_response)

    async def run_an_action(self, id: UUID, serverPowerUpdateRequest: ServerPowerUpdateRequest, token: str) -> None:
        """
        - [POST] /servers/{server_id}/action
        - 202 (need polling)
        :return: None
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/servers/{id}/action',
            headers={OA_TOKEN_HEADER_FIELD: token},
            data=serverPowerUpdateRequest.serialize()
        )
        await self.request_openstack(method='POST', request=oa_request)
        return None

    async def delete_server(self, id: str, token: str) -> None:
        """
        - [DELETE] /servers/{server_id}
        - 204 (need polling)
        :return: None
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/servers/{id}',
            headers={'Content-Type': 'application/json', OA_TOKEN_HEADER_FIELD: token},
        )
        oa_response = await self.request_openstack(method='DELETE', request=oa_request)
        return None

    async def create_console(self, id: UUID, token: str) -> Optional[str]:
        """
        - [POST] /servers/{server_id}/remote-consoles (v2.95)
        - 200 : vnc 콘솔 정보
        :return: str (url of vnc)
        """
        data_dict = {
            "remote_console": {
                "protocol": "vnc",
                "type": "novnc"
            }
        }
        serialized_data = json.dumps(data_dict)
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/servers/{id}/remote-consoles',
            headers={'Content-Type': 'application/json', OA_TOKEN_HEADER_FIELD: token,
                     'X-OpenStack-Nova-API-Version': '2.95'},
            data=serialized_data
        )
        oa_response = await self.request_openstack(method='POST', request=oa_request)
        response_dict = oa_response.model_dump()['data'].get('remote_console')
        return response_dict.get('url') if response_dict is not None else None

    async def attach_volume_to_instance(self, id: UUID, serverVolumeUpdateRequest: ServerVolumeUpdateRequest,
                                        token: str):
        """
        - [POST] /servers/{server_id}/os-volume_attachments
        - 200 : volumeAttachments (need polling)
        :return: None
        """
        oa_request = OpenstackBaseRequest(url=f'{self.COMPONENT_URL}/servers/{id}/os-volume_attachments',
                                          headers={'Content-Type': 'application/json', OA_TOKEN_HEADER_FIELD: token},
                                          data=serverVolumeUpdateRequest.serialize_for_attach())
        oa_response = await self.request_openstack(method='POST', request=oa_request)
        return None

    async def detach_volume_to_instance(self, id: UUID, serverVolumeUpdateRequest: ServerVolumeUpdateRequest,
                                        token: str) -> None:
        """
        - [DELETE] /servers/{server_id}/os-volume_attachments/{volume_id}
        - 202 : None (need polling)
        :return: None
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/servers/{id}/os-volume_attachments/{serverVolumeUpdateRequest.volume_id}',
            headers={'Content-Type': 'application/json', OA_TOKEN_HEADER_FIELD: token},
        )
        oa_response = await self.request_openstack(method='DELETE', request=oa_request)
        return None

    async def show_rate_and_absolute_limits(self, token: str) -> ServerRemainLimitDto:
        """
        - [GET] /limits
        - 200 : limit detail (limits.absolute)
        :return: ServerRemainLimitDto
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/limits',
            headers={OA_TOKEN_HEADER_FIELD: token}
        )
        oa_response = await self.request_openstack(method='GET', request=oa_request)
        return ServerRemainLimitDto.deserialize(oa_response)

    async def list_flavors_with_details(self, token: str) -> List[FlavorDto]:
        """
        - [GET] /flavors/detail
        - 200 : list of flavor details
        :return: List[FlavorDto]
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/flavors/detail',
            headers={OA_TOKEN_HEADER_FIELD: token}
        )
        oa_response = await self.request_openstack(method='GET', request=oa_request)
        return FlavorDto.deserialize(oa_response)

    async def show_flavor_details(self, flavor_id: str, token: str) -> FlavorDto:
        """
        - [GET] /flavors/{flavor_id}
        - 200 : flavor detail
        : return: FlavorDto (존재하지 않는다면 에러 발생)
        """
        oa_request = OpenstackBaseRequest(
            url=f'{self.COMPONENT_URL}/flavors/{flavor_id}',
            headers={OA_TOKEN_HEADER_FIELD: token}
        )
        oa_response = await self.request_openstack(method='GET', request=oa_request)
        return FlavorDto.deserialize(oa_response, many=False)
