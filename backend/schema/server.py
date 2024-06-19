import json
from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID
from pydantic import Field, BaseModel

from backend.core.config import get_setting
from backend.model.server import ServerStatus
from backend.schema.oa_base import OpenstackBaseResponse
from backend.schema.query import PaginationQueryBasic, SortQueryBasic, FilterBasic
from backend.schema.volume import RootVolumeCreateRequest

SETTINGS = get_setting()


class ServerQuery(PaginationQueryBasic, SortQueryBasic, FilterBasic):
    """
    - 검색조건:
        - server_id(equal, in, not)
        - name(equal, like)
    - 정렬 조건
        - name
        - created_at
    """
    sort_by: Optional[str] = Field(default=None, pattern=f'^(created_at|name)$')
    server_id: Optional[str] = Field(default=None, pattern=f'^(eq|in|not):.+', is_Filter=True)
    name: Optional[str] = Field(default=None, pattern=f'^(eq|like):.+', is_Filter=True)


class ServerRequestBasic(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field("", max_length=255)
    flavor_id: str


class ServerCreateRequest(ServerRequestBasic):
    volume: RootVolumeCreateRequest

    def serialize(self) -> str:
        return json.dumps(
            {
                "server": {
                    "name": self.name,
                    "flavorRef": "1",
                    "networks": [
                        {
                            "uuid": f"{SETTINGS.OPENSTACK_PRIVATE_NETWORK_ID}"
                        }
                    ],
                    "block_device_mapping_v2": [
                        {
                            "boot_index": 0,
                            "uuid": f"{self.volume.image_id}",
                            "source_type": "image",
                            "destination_type": "volume",
                            "delete_on_termination": True,
                            "volume_size": self.volume.size,
                            "volume_type": SETTINGS.OPENSTACK_DEFAULT_VOLUME_TYPE
                        }
                    ],
                    "security_groups": [
                        {
                            "name": "default"
                        }
                    ]
                }
            }
        )


class ServerUpdateInfoRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=255)

    def serialize(self) -> str:
        """
        user input -> oa_request
        name, description은 없다면 필드 자체를 빼고 보내야 한다
        """
        data_dict = {
            "name": self.name,
            "description": self.description
        }
        if not self.name:
            del data_dict["name"]
        if not self.description:
            del data_dict["description"]
        return json.dumps({"server": data_dict})


class PowerState(str, Enum):
    START = 'start'
    STOP = 'stop'
    PAUSE = 'pause'
    UNPAUSE = 'unpause'
    HARD_REBOOT = 'hard-reboot'
    SOFT_REBOOT = 'soft-reboot'


class ServerPowerUpdateRequest(BaseModel):
    power_state: PowerState

    def serialize(self) -> str:
        """
        user_input -> oa_response
        """
        data_dict = {}
        if self.power_state in (PowerState.START, PowerState.STOP):
            data_dict[f'os-{self.power_state.value}'] = None
        elif self.power_state in (PowerState.PAUSE, PowerState.UNPAUSE):
            data_dict[f'{self.power_state.value}'] = None
        else:
            # hard-reboot => HARD
            # soft-reboot => SOFT
            data_dict['reboot'] = {'type': 'HARD' if self.power_state == PowerState.HARD_REBOOT else 'SOFT'}
        return json.dumps(data_dict)


class ServerVolumeUpdateRequest(BaseModel):
    """
    server와 연결 혹은 해제를 위한 입력을 처리
    """
    volume_id: UUID

    def serialize_for_attach(self) -> str:
        data_dict = {
            "volumeAttachment": {
                "volumeId": f"{self.volume_id}"
            }
        }
        return json.dumps(data_dict)


class ServerDto(BaseModel):
    """
    db server와 연결됨 (need to exclude status)
    """
    server_id: UUID
    name: str
    description: Optional[str]
    fk_project_id: UUID
    fk_flavor_id: str
    fk_network_id: Optional[UUID]
    fk_port_id: Optional[UUID]
    fixed_address: Optional[str]
    status: ServerStatus
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = Field(default=None)

    @staticmethod
    def deserialize(oa_response: OpenstackBaseResponse) -> 'ServerDto':
        """
        서버 정보 & interface 조회 -> oa_response -> dto -> db 서버 생성
        """
        response_dict = oa_response.model_dump()
        server_response = response_dict['data']['server']
        return ServerDto(
            server_id=UUID(server_response.get('id')),
            name=server_response['name'],
            description=None,  # oa 상에는 없음
            fk_project_id=UUID(SETTINGS.OPENSTACK_PROJECT_ID),
            fk_flavor_id=server_response.get('flavor').get('id'),
            fk_network_id=UUID(SETTINGS.OPENSTACK_PRIVATE_NETWORK_ID),
            fk_port_id=None,  # os-interface 통해 set
            fixed_address=None,  # os-interface 통해 set
            status=server_response.get('status'),
            created_at=server_response.get('created'),
            updated_at=server_response.get('updated')
        )

    @staticmethod
    def deserialize_volumes(oa_response: OpenstackBaseResponse) -> List[UUID]:
        response_dict = oa_response.model_dump()
        server_response = response_dict['data']['server']
        volumes = server_response.get('os-extended-volumes:volumes_attached')
        return [UUID(volume.get('id')) for volume in volumes]


class ServerUpdateDto(BaseModel):
    """
    server update 요청 (2.95)의 결과로 db 반영하기 위함
    """
    name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)

    def deserialize(oa_response: OpenstackBaseResponse) -> 'ServerUpdateDto':
        """
        user input -> oa_request
        name, description은 없다면 필드 자체를 빼고 보내야 한다
        """
        response_dict = oa_response.model_dump()
        server_response = response_dict['data']['server']
        return ServerUpdateDto(
            name=server_response.get('name'),
            description=server_response.get('description')
        )


class ServerNetInterfaceDto(BaseModel):
    """
    os-interface를 통해 얻은 네트워크 관련 값
    """
    port_id: Optional[UUID] = Field(default=None)
    fixed_address: Optional[str] = Field(default=None)

    @staticmethod
    def deserialize(oa_response: OpenstackBaseResponse) -> Optional['ServerNetInterfaceDto']:
        networkAttachments = oa_response.model_dump()['data'].get('interfaceAttachments')
        if networkAttachments:
            interface_response = networkAttachments[0]  # network interface는 하나로 고정
            return ServerNetInterfaceDto(
                port_id=interface_response.get('port_id'),
                fixed_address=interface_response.get('fixed_ips')[0].get('ip_address')
            )
        else:
            return None


class FlavorDto(BaseModel):
    id: str
    name: str
    ram: int
    disk: int
    vcpus: int

    @staticmethod
    def deserialize(oa_response: OpenstackBaseResponse, many: Optional[bool] = True) -> List['FlavorDto'] | 'FlavorDto':
        response_dict = oa_response.model_dump()
        if not many:
            flavor_response = response_dict['data']['flavor']
            return FlavorDto(
                id=flavor_response['id'],
                name=flavor_response['name'],
                ram=flavor_response['ram'],
                disk=flavor_response['disk'],
                vcpus=flavor_response['vcpus']
            )

        flavor_list_response = response_dict['data']['flavors']
        return [FlavorDto(
            id=flavor['id'],
            name=flavor['name'],
            ram=flavor['ram'],
            disk=flavor['disk'],
            vcpus=flavor['vcpus']) for flavor in flavor_list_response]


class ImageDto(BaseModel):
    id: UUID
    name: Optional[str] = Field(default=None)
    disk_format: Optional[str] = Field(default=None)
    status: str
    min_disk: Optional[int] = Field(default=None)
    min_ram: Optional[int] = Field(default=None)
    size: Optional[int] = Field(default=None)
    virtual_size: Optional[int] = Field(default=None)

    @staticmethod
    def deserialize(oa_response: OpenstackBaseResponse, many: Optional[bool] = False) -> 'ImageDto' | List['ImageDto']:
        response_dict = oa_response.model_dump()
        if not many:
            image_response = response_dict['data']
            return ImageDto(
                id=UUID(image_response.get('id')),
                name=image_response.get('name'),
                disk_format=image_response.get('disk_format'),
                status=image_response.get('status'),
                min_disk=image_response.get('min_disk'),
                min_ram=image_response.get('min_ram'),
                size=image_response.get('size'),
                virtual_size=image_response.get('virtual_size')
            )
        images = response_dict['data']['images']
        return [ImageDto(
            id=UUID(image_response.get('id')),
            name=image_response.get('name'),
            disk_format=image_response.get('disk_format'),
            status=image_response.get('status'),
            min_disk=image_response.get('min_disk'),
            min_ram=image_response.get('min_ram'),
            size=image_response.get('size'),
            virtual_size=image_response.get('virtual_size')
        ) for image_response in images]


class ServerRemainLimitDto(BaseModel):
    remain_instances: int
    remain_cores: int
    remain_rams: int

    @staticmethod
    def deserialize(oa_response: OpenstackBaseResponse) -> 'ServerRemainLimitDto':
        response_dict = oa_response.model_dump()
        quota_response = response_dict['data']['limits']
        server_quota = quota_response.get('absolute')
        return ServerRemainLimitDto(
            remain_instances=server_quota.get('maxTotalInstances') - server_quota.get('totalInstancesUsed'),
            remain_cores=server_quota.get('maxTotalCores') - server_quota.get('totalCoresUsed'),
            remain_rams=server_quota.get('maxTotalRAMSize') - server_quota.get('totalRAMUsed')
        )
