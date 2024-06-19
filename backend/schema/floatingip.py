from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
import json

from backend.model.floatingip import FloatingipStatus
from backend.schema.oa_base import OpenstackBaseResponse
from backend.core.config import get_setting
from backend.schema.query import PaginationQueryBasic, SortQueryBasic, FilterBasic

SETTINGS = get_setting()


class FloatingipQuery(PaginationQueryBasic, SortQueryBasic, FilterBasic):
    """
    - 검색조건:
        - floatingip_id (equal, in, not)
        - ip_address (equal, like)
    - 정렬조건:
        - created_at
    """
    sort_by: Optional[str] = Field(default=None, pattern=f'^(created_at)$')
    floatingip_id: Optional[str] = Field(default=None, pattern=f'^(eq|in|not):.+', isFilter=True)
    ip_address: Optional[str] = Field(default=None, pattern=f'^(eq|like):.+', isFilter=True)


class FloatingipCreateRequest(BaseModel):
    description: Optional[str] = Field("", max_length=255)

    def serialize(self) -> str:
        """
        user input -> oa_request
        """
        data_dict = {
            "floating_network_id": SETTINGS.OPENSTACK_PUBLIC_NETWORK_ID,  # 고정
            "port_id": None,
            "subnet_id": SETTINGS.OPENSTACK_SUBNET_ID,  # 고정
            "description": self.description
        }
        if not self.description:
            del data_dict["description"]
        return json.dumps({"floatingip": data_dict})


class FloatingipDto(BaseModel):
    """
    db table과 연결됨 (need to exclude status)
    """
    floatingip_id: UUID
    ip_address: str
    fk_project_id: UUID
    fk_port_id: Optional[UUID] = Field(default=None)
    fk_network_id: UUID
    status: FloatingipStatus
    description: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = Field(default=None)

    @staticmethod
    def deserialize(oa_response: OpenstackBaseResponse) -> 'FloatingipDto':
        """
        oa_response -> dto
        """
        response_dict = oa_response.model_dump()
        floatingip_response = response_dict['data']['floatingip']
        return FloatingipDto(
            floatingip_id=floatingip_response['id'],
            ip_address=floatingip_response['floating_ip_address'],
            fk_project_id=UUID(SETTINGS.OPENSTACK_PROJECT_ID),  # 고정
            fk_port_id=UUID(floatingip_response['port_id']) if floatingip_response['port_id'] else None,
            fk_network_id=UUID(floatingip_response['floating_network_id']),
            status=floatingip_response['status'],
            description=floatingip_response['description'],
            created_at=floatingip_response['created_at'],
            updated_at=floatingip_response['updated_at'],
            deleted_at=None
        )


class FloatingipUpdateRequest(BaseModel):
    description: Optional[str] = Field(None, max_length=255)

    def serialize(self) -> str:
        """
        user input -> oa_request
        """
        data_dict = {
            "description": self.description
        }
        if not self.description:
            del data_dict["description"]
        return json.dumps({"floatingip": data_dict})


class FloatingipUpdatePortRequest(BaseModel):
    port_id: Optional[UUID] = Field(None)  # None이면 포트 연결 해제

    def serialize(self) -> str:
        data_dict = {
            "port_id": f"{self.port_id}" if self.port_id else None,
        }
        return json.dumps({"floatingip": data_dict})


class FloatingipRemainLimitDto(BaseModel):
    remain_cnt: int

    @staticmethod
    def deserialize(oa_response: OpenstackBaseResponse) -> 'FloatingipRemainLimitDto':
        response_dict = oa_response.model_dump()
        quota_response = response_dict['data']['quota']
        floatingip_quota = quota_response.get('floatingip')
        return FloatingipRemainLimitDto(
            remain_cnt=floatingip_quota.get('limit') - floatingip_quota.get('used') - floatingip_quota.get('reserved')
        )
