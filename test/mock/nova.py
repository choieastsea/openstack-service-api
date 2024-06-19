import uuid
from datetime import datetime
from uuid import UUID
from typing import List, Tuple

from backend.client.nova import NovaClient
from backend.core.config import get_setting
from backend.core.exception import OpenstackClientException
from backend.model.server import ServerStatus, Server
from backend.schema.oa_base import OpenstackBaseResponse
from backend.schema.server import ServerDto, FlavorDto

SETTINGS = get_setting()


class NovaClientMock(NovaClient):
    def __init__(self) -> None:
        super().__init__()

    async def show_flavor_details_success(self, flavor_id: str, token: str):
        return None

    @staticmethod
    def show_flavor_details_basic() -> FlavorDto:
        """
        4 core, 8GB ram, 16GB disk
        """
        return FlavorDto(
            id="1",
            name="test flavor(4/8/16)",
            ram=8,
            disk=16,
            vcpus=4
        )

    async def show_flavor_details_not_found(self, flavor_id: str, token: str):
        oa_response = OpenstackBaseResponse(status=404, headers={}, data={})
        raise OpenstackClientException(oa_response)

    @staticmethod
    def create_server_success(server_id: UUID) -> UUID:
        return server_id

    @staticmethod
    def show_server_details_success(server_id: UUID, request: dict) -> Tuple[ServerDto, List[UUID]]:
        """
        요청 정보를 기반으로 ServerDto를 생성하여 리턴
        """
        serverDto = ServerDto(
            server_id=server_id,
            name=request.get('name'),
            description=request.get('description'),
            fk_project_id=SETTINGS.OPENSTACK_PROJECT_ID,
            fk_flavor_id=request.get('flavor_id'),
            fk_network_id=None,
            fk_port_id=None,
            fixed_address=None,
            status=ServerStatus.BUILD,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            deleted_at=None,
        )
        volume_id_list = [uuid.uuid4()]
        return serverDto, volume_id_list

    @staticmethod
    def show_server_details_with_status(server: Server, status: ServerStatus) -> ServerDto:
        """
        해당 상태의 server dto를 반환
        """
        return ServerDto(**server.__dict__, status=status)

    @staticmethod
    def show_server_details_success_with_active_server(server: Server, volume_id: UUID) -> Tuple[ServerDto, List[UUID]]:
        """
        서버를 active 상태로 반환한다
        """
        serverDto = ServerDto(**server.__dict__, status=ServerStatus.ACTIVE)
        volume_id_list = [volume_id]
        return serverDto, volume_id_list

    @staticmethod
    def show_server_details_fail_with_error_server(server: Server) -> Tuple[ServerDto, None]:
        """
        서버를 active 상태로 반환한다
        """
        serverDto = ServerDto(**server.__dict__, status=ServerStatus.ERROR)
        return serverDto, None


nova_client_mock = NovaClientMock()
