from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from backend.client import neutron_client, nova_client, cinder_client
from backend.core.exception import OpenstackClientException
from backend.model.floatingip import Floatingip, FloatingipStatus
from backend.model.server import Server, ServerStatus
from backend.model.volume import Volume, VolumeStatus


class ServerOverallResponse(BaseModel):
    """
    다른 모델에서 연결된 서버를 보여줄 때, 필요한 스키마
    """
    server_id: UUID
    name: str

    @staticmethod
    def mapper(server: Server) -> Optional['ServerOverallResponse']:
        if server is None:
            return None
        return ServerOverallResponse(
            server_id=server.server_id,
            name=server.name
        )


class FloatingipOverallResponse(BaseModel):
    floatingip_id: UUID
    ip_address: str

    @staticmethod
    def mapper(floatingip: Floatingip) -> Optional['FloatingipOverallResponse']:
        if floatingip is None:
            return None
        return FloatingipOverallResponse(
            floatingip_id=floatingip.floatingip_id,
            ip_address=floatingip.ip_address
        )


class VolumeOverallResponse(BaseModel):
    volume_id: UUID
    name: str
    volume_type: str
    size: int
    is_root: Optional[bool] = None

    @staticmethod
    def mapper(el: Volume | List[Volume]) -> Optional['VolumeOverallResponse' | List['VolumeOverallResponse']]:
        if el is None:
            return None
        if isinstance(el, Volume):
            volume = el
            return VolumeOverallResponse(
                volume_id=volume.volume_id,
                name=volume.name,
                volume_type=volume.volume_type,
                size=volume.size,
                is_root=volume.is_root_volume
            )
        volume_list = el
        return [VolumeOverallResponse.mapper(volume) for volume in volume_list]


class FloatingipResponse(BaseModel):
    floatingip_id: UUID
    ip_address: str
    project_id: UUID
    server: Optional[ServerOverallResponse]
    network_id: UUID
    status: str
    description: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    @staticmethod
    async def mapper(el: Floatingip | list[Floatingip], token: str) -> 'FloatingipResponse' | List[
        'FloatingipResponse']:
        if isinstance(el, Floatingip):
            floatingip = el
            server = await floatingip.awaitable_attrs.server
            # get latest floatingip status
            status = await get_floatingip_status_by_id_or_deleted(id=floatingip.floatingip_id, token=token)
            return FloatingipResponse(
                floatingip_id=floatingip.floatingip_id,
                ip_address=floatingip.ip_address,
                project_id=floatingip.fk_project_id,
                server=ServerOverallResponse.mapper(server),
                network_id=floatingip.fk_network_id,
                status=status,
                description=floatingip.description,
                created_at=floatingip.created_at,
                updated_at=floatingip.updated_at,
                deleted_at=floatingip.deleted_at
            )
        floatingip_list = el
        return [await FloatingipResponse.mapper(el=floatingip, token=token) for floatingip in floatingip_list]


async def get_floatingip_status_by_id_or_deleted(id: UUID, token: str) -> FloatingipStatus:
    """
    NEUTRON 이용하여 floatingip의 상태를 조회한다.

    해당 id가 DB에 존재하지만, openstack에 존재하지 않는 경우에는 floatingip의 상태를 deleted로 간주한다.
    :param id: floatingip id
    :param token: 인증 토큰
    :return: FloatingipStatus(유동ip 상태)
    """
    try:
        floatingipDto = await neutron_client.show_floating_ip_details(id, token)
        return floatingipDto.status
    except OpenstackClientException as e:
        if e.status == 404:
            return FloatingipStatus.DELETED
        else:
            raise e


class ServerResponse(BaseModel):
    """
    연관된 자원도 overall하게 보여줘야한다
    """
    server_id: UUID
    name: str
    description: Optional[str]
    project_id: UUID
    flavor_id: str
    network_id: Optional[UUID]
    port_id: Optional[UUID]
    fixed_address: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
    volumes: List[VolumeOverallResponse]
    floatingip: Optional[FloatingipOverallResponse]

    @staticmethod
    async def mapper(el: Server | List[Server], token: str) -> 'ServerResponse' | List['ServerResponse']:
        if isinstance(el, Server):
            server = el
            # awaitable relationships
            volumes = await server.awaitable_attrs.volumes
            floatingip = await server.awaitable_attrs.floatingip
            # get latest server status
            cur_status = await get_server_status_by_id_or_deleted(id=server.server_id, token=token)
            return ServerResponse(
                server_id=server.server_id,
                name=server.name,
                description=server.description,
                project_id=server.fk_project_id,
                flavor_id=server.fk_flavor_id,
                network_id=server.fk_network_id,
                port_id=server.fk_port_id,
                fixed_address=server.fixed_address,
                status=cur_status,
                created_at=server.created_at,
                updated_at=server.updated_at,
                deleted_at=server.deleted_at,
                volumes=VolumeOverallResponse.mapper(volumes) if volumes else [],
                floatingip=FloatingipOverallResponse.mapper(floatingip)
            )
        server_list = el
        return [await ServerResponse.mapper(el=server, token=token) for server in server_list]


async def get_server_status_by_id_or_deleted(id: UUID, token: str) -> ServerStatus:
    """
    NOVA 이용하여 서버의 상태를 조회한다.

    해당 id가 DB에 존재하지만, openstack에 존재하지 않는 경우에는 서버의 상태를 deleted로 간주한다.

    :param id: server id
    :param token: 인증 토큰
    :return: ServerStatus(서버 상태)
    """
    try:
        serverDto = await nova_client.show_server_details(id=id, token=token)
        return serverDto.status
    except OpenstackClientException as e:
        if e.status == 404:
            return ServerStatus.DELETED
        else:
            raise e


class VolumeResponse(BaseModel):
    volume_id: UUID
    name: str
    description: Optional[str] = Field(default=None)
    volume_type: str
    size: int
    server: Optional[ServerOverallResponse]
    project_id: UUID
    image_id: Optional[UUID] = Field(default=None)
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)

    @staticmethod
    async def mapper(el: Volume | list[Volume], token: str) -> 'VolumeResponse' | List['VolumeResponse']:
        if isinstance(el, Volume):
            volume = el
            # awaitable attrs
            server_attached = await volume.awaitable_attrs.server
            # get latest volume status
            status = await get_volume_status_by_id_or_deleted(id=volume.volume_id, token=token)
            return VolumeResponse(
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
        return [await VolumeResponse.mapper(el=volume, token=token) for volume in volume_list]


async def get_volume_status_by_id_or_deleted(id: UUID, token: str) -> VolumeStatus:
    """
    CINDER 이용하여 볼륨의 상태를 조회한다.

    해당 id가 DB에 존재하지만, openstack에 존재하지 않는 경우에는 볼륨의 상태를 deleted로 간주한다.
    :param id: volume id
    :param token: 인증 토큰
    :return: VolumeStatus(볼륨 상태)
    """
    try:
        volumeDto = await cinder_client.show_volume_detail(id=id, token=token)
        return volumeDto.status
    except OpenstackClientException as e:
        if e.status == 404:
            return VolumeStatus.DELETED
        else:
            raise e
