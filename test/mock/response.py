from typing import List

from backend.model.floatingip import Floatingip, FloatingipStatus
from backend.model.server import Server, ServerStatus
from backend.model.volume import Volume, VolumeStatus
from backend.schema.response import FloatingipResponse, ServerOverallResponse, ServerResponse, VolumeOverallResponse, \
    FloatingipOverallResponse, VolumeResponse


class FloatingipResponseMock(FloatingipResponse):
    @staticmethod
    async def mapper(el: Floatingip | list[Floatingip], token: str = '') -> 'FloatingipResponseMock' | List[
        'FloatingipResponseMock']:
        if isinstance(el, Floatingip):
            floatingip = el
            server = await floatingip.awaitable_attrs.server
            return FloatingipResponseMock(
                floatingip_id=floatingip.floatingip_id,
                ip_address=floatingip.ip_address,
                project_id=floatingip.fk_project_id,
                server=ServerOverallResponse.mapper(server),
                network_id=floatingip.fk_network_id,
                status=FloatingipStatus.ACTIVE if server else FloatingipStatus.DOWN,
                description=floatingip.description,
                created_at=floatingip.created_at,
                updated_at=floatingip.updated_at,
                deleted_at=floatingip.deleted_at
            )
        floatingip_list = el
        return [await FloatingipResponseMock.mapper(el=floatingip) for floatingip in floatingip_list]


class VolumeResponseMock(VolumeResponse):
    @staticmethod
    async def mapper(el: Volume | List[Volume],
                     token: str = '',
                     status: VolumeStatus = None) -> 'VolumeResponseMock' | List['VolumeResponseMock']:
        if isinstance(el, Volume):
            volume = el
            # awaitable relationships
            server_attached = await volume.awaitable_attrs.server
            if server_attached:
                status = VolumeStatus.IN_USE
            elif status is None:
                status = VolumeStatus.AVAILABLE
            return VolumeResponseMock(
                volume_id=volume.volume_id,
                name=volume.name,
                description=volume.description,
                volume_type=volume.volume_type,
                size=volume.size,
                server=ServerOverallResponse.mapper(server_attached),
                project_id=volume.fk_project_id,
                image_id=volume.fk_image_id,
                status=status,
                created_at=volume.created_at,
                updated_at=volume.updated_at,
                deleted_at=volume.deleted_at
            )

        volume_list = el
        return [await VolumeResponseMock.mapper(el=volume) for volume in volume_list]


class ServerResponseMock(ServerResponse):
    @staticmethod
    async def mapper(el: Server | List[Server],
                     token: str = '',
                     status: ServerStatus = None) -> 'ServerResponseMock' | List['ServerResponseMock']:
        if isinstance(el, Server):
            server = el
            # awaitable relationships
            volumes = await server.awaitable_attrs.volumes
            floatingip = await server.awaitable_attrs.floatingip
            return ServerResponseMock(
                server_id=server.server_id,
                name=server.name,
                description=server.description,
                project_id=server.fk_project_id,
                flavor_id=server.fk_flavor_id,
                network_id=server.fk_network_id,
                port_id=server.fk_port_id,
                fixed_address=server.fixed_address,
                status=ServerStatus.ACTIVE if not status else status,
                created_at=server.created_at,
                updated_at=server.updated_at,
                deleted_at=server.deleted_at,
                volumes=VolumeOverallResponse.mapper(volumes) if volumes else [],
                floatingip=FloatingipOverallResponse.mapper(floatingip)
            )

        server_list = el
        return [await ServerResponseMock.mapper(el=server) for server in server_list]
