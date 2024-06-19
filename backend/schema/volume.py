from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
import json

from backend.core.config import get_setting
from backend.model.volume import VolumeStatus
from backend.schema.oa_base import OpenstackBaseResponse
from backend.schema.query import PaginationQueryBasic, SortQueryBasic, FilterBasic

SETTINGS = get_setting()


class VolumeQuery(PaginationQueryBasic, SortQueryBasic, FilterBasic):
    """
    - 검색조건:
        - volume_id (equal, in, not)
        - name (equal, like)
    - 정렬 조건
        - name
        - created_at
    """
    sort_by: Optional[str] = Field(default=None, pattern=f'^(created_at|name)$')
    volume_id: Optional[str] = Field(default=None, pattern=f'^(eq|in|not):.+', isFilter=True)
    name: Optional[str] = Field(default=None, pattern=f'^(eq|like):.+', is_Filter=True)


class VolumeCreateRequest(BaseModel):
    """
    image가 아닌 volume을 만들기 위한 request
    """
    size: int = Field(ge=1)
    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, max_length=255)

    def serialize(self) -> str:
        """
        user input-> oa_request
        """
        return json.dumps({
            "volume": {
                "size": self.size,
                "name": self.name,
                "description": self.description,
                "multiattach": False,
                "volume_type": SETTINGS.OPENSTACK_DEFAULT_VOLUME_TYPE
            }
        })


class RootVolumeCreateRequest(BaseModel):
    """
    root volume을 위한 request (while creating server)
    """
    name: str = Field(max_length=255)
    size: int = Field(ge=1)
    image_id: UUID  # image 기반 bootable disk로 생성


class VolumeDto(BaseModel):
    """
    db table과 연결됨 (need to exclude status)
    """
    volume_id: UUID
    name: str
    description: Optional[str] = Field(default=None)
    volume_type: str
    size: int
    fk_server_id: Optional[UUID] = Field(default=None)
    fk_project_id: UUID
    fk_image_id: Optional[UUID] = Field(default=None)
    status: VolumeStatus
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)

    @staticmethod
    def deserialize(oa_response: OpenstackBaseResponse) -> 'VolumeDto':
        """
        oa_response -> dto
        """
        response_dict = oa_response.model_dump()
        volume_response = response_dict['data']['volume']
        is_server_attached = volume_response.get('attachments')
        is_bootable = volume_response.get('volume_image_metadata')
        return VolumeDto(
            volume_id=UUID(volume_response['id']),
            name=volume_response['name'],
            description=volume_response['description'],
            volume_type=volume_response['volume_type'],
            size=volume_response['size'],
            fk_server_id=volume_response['attachments'][0].get('server_id') if is_server_attached else None,
            fk_project_id=UUID(SETTINGS.OPENSTACK_PROJECT_ID),  # 고정
            fk_image_id=UUID(volume_response['volume_image_metadata'].get('image_id')) if is_bootable else None,
            status=volume_response['status'],
            created_at=volume_response['created_at'],
            updated_at=volume_response['updated_at'],
            deleted_at=None
        )


class VolumeUpdateInfoRequest(BaseModel):
    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, max_length=255)

    def serialize(self) -> str:
        """
        user_input -> string for oa_request
        """
        data_dict = {
            "name": self.name,
            "description": self.description,
        }
        if self.description is None:
            # description이 field에 없다면 굳이 업데이트 하지 않음
            del data_dict['description']

        return json.dumps({
            "volume": data_dict
        })


class VolumeSizeUpdateRequest(BaseModel):
    new_size: int = Field(ge=2)  # 기존 보다 커야함

    def serialize(self) -> str:
        data_dict = {
            "os-extend": {
                "new_size": self.new_size
            }
        }
        return json.dumps(data_dict)


class VolumeRemainLimitDto(BaseModel):
    """
    남은 볼륨 사용량을 위한 dto
    """
    remain_cnt: int  # 추가 가능한 볼륨 갯수
    remain_size: int  # 추가 가능한 볼륨 용량

    @staticmethod
    def deserialize(oa_response: OpenstackBaseResponse) -> 'VolumeRemainLimitDto':
        response_dict = oa_response.model_dump()['data']
        absolute_limits = response_dict['limits']['absolute']
        remain_cnt = absolute_limits.get('maxTotalVolumes') - absolute_limits.get('totalVolumesUsed')
        remain_size = absolute_limits.get('maxTotalVolumeGigabytes') - absolute_limits.get('totalGigabytesUsed')
        return VolumeRemainLimitDto(
            remain_size=remain_size,
            remain_cnt=remain_cnt
        )
