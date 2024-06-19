from sqlalchemy import Column, Uuid, String, DateTime, ForeignKey
from datetime import datetime
import enum
from sqlalchemy.orm import relationship
from uuid import UUID

from backend.core.db import Base


class FloatingipStatus(str, enum.Enum):
    ACTIVE = 'ACTIVE'
    DOWN = 'DOWN'
    ERROR = 'ERROR'

    DELETED = 'DELETED'  # for soft delete


class Floatingip(Base):
    __tablename__ = 'floatingip'
    floatingip_id: UUID = Column(
        Uuid(as_uuid=True), primary_key=True, comment='floatingip id')
    ip_address: str = Column(String(15), nullable=False,
                             comment='floating ip address')
    fk_project_id: UUID = Column(Uuid(as_uuid=True))
    fk_port_id: UUID = Column(Uuid(as_uuid=True), ForeignKey('server.fk_port_id'), nullable=True,
                              comment='연결된 포트')
    fk_network_id: UUID = Column(
        Uuid(as_uuid=True), nullable=True, comment='public network id')
    description: str = Column(String(255))
    created_at: datetime = Column(DateTime, comment='생성시간')
    updated_at: datetime = Column(DateTime, comment='수정시간')
    deleted_at: datetime = Column(DateTime, nullable=True, comment='삭제시간')

    server = relationship('Server', back_populates='floatingip')

    @property
    def deleted(self) -> bool:
        return self.deleted_at is not None
