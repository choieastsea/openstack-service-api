import datetime
import uuid

from backend.client.neutron import NeutronClient
from backend.core.config import get_setting
from backend.core.exception import OpenstackClientException
from backend.model.floatingip import Floatingip, FloatingipStatus
from backend.schema.floatingip import FloatingipDto, FloatingipCreateRequest
from backend.schema.oa_base import OpenstackBaseResponse

SETTINGS = get_setting()


class NeutronClientMock(NeutronClient):
    def __init__(self) -> None:
        super().__init__()

    async def create_floating_ip_success(self, token: str,
                                         floatingipCreateRequest: FloatingipCreateRequest) -> FloatingipDto:
        floatingipDto = FloatingipDto(
            floatingip_id=uuid.uuid4(),
            ip_address='123.123.123.123',
            fk_project_id=SETTINGS.OPENSTACK_PROJECT_ID,
            fk_port_id=None,
            fk_network_id=SETTINGS.OPENSTACK_PUBLIC_NETWORK_ID,
            status='DOWN',
            description=floatingipCreateRequest.description,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
            deleted_at=None
        )
        return floatingipDto

    async def create_floating_ip_409(self, token: str, floatingipCreateRequest: FloatingipCreateRequest):
        """
        가용 공간이 없는 경우 409
        """
        oa_response = OpenstackBaseResponse(status=409, data={'NeutronError': {'type': 'IpAddressGenerationFailure',
                                                                               'message': f'No more IP addresses available on network {SETTINGS.OPENSTACK_PUBLIC_NETWORK_ID}',
                                                                               'detail': None}})
        raise OpenstackClientException(oa_response)

    async def delete_floating_ip_success(self, id: uuid.UUID, token: str):
        return None

    @staticmethod
    def update_floating_ip_success(floatingip: Floatingip):
        return FloatingipDto(
            **floatingip.__dict__,
            status=FloatingipStatus.ACTIVE if floatingip.fk_port_id else FloatingipStatus.DOWN
        )