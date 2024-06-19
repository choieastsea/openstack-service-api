import enum
from datetime import datetime
from typing import List
from uuid import UUID
from sqlalchemy import Column, Uuid, String, DateTime
from sqlalchemy.orm import Mapped, relationship

from backend.core.db import Base
from backend.model.floatingip import Floatingip
from backend.model.volume import Volume


class ServerStatus(str, enum.Enum):
    ACTIVE = 'ACTIVE'
    BUILD = 'BUILD'
    DELETED = 'DELETED'
    ERROR = 'ERROR'
    HARD_REBOOT = 'HARD_REBOOT'
    MIGRATING = 'MIGRATING'
    PASSWORD = 'PASSWORD'
    PAUSED = 'PAUSED'
    REBOOT = 'REBOOT'
    REBUILD = 'REBUILD'
    RESCUE = 'RESCUE'
    RESIZE = 'RESIZE'
    REVERT_RESIZE = 'REVERT_RESIZE'
    SHELVED = 'SHELVED'
    SHELVED_OFFLOADED = 'SHELVED_OFFLOADED'
    SHUTOFF = 'SHUTOFF'
    SOFT_DELETED = 'SOFT_DELETED'
    SUSPENDED = 'SUSPENDED'
    UNKNOWN = 'UNKNOWN'
    VERIFY_RESIZE = 'VERIFY_RESIZE'


class Server(Base):
    __tablename__ = 'server'
    server_id: UUID = Column(
        Uuid(as_uuid=True), primary_key=True, comment='server id')
    name: str = Column(String(255), nullable=False, comment='server name')
    description: str = Column(String(255))
    fk_project_id: UUID = Column(Uuid(as_uuid=True))
    fk_flavor_id: str = Column(String(255), comment='사양 flavor id')
    fk_network_id: UUID = Column(
        Uuid(as_uuid=True), nullable=True, comment='private network id')
    fk_port_id: UUID = Column(
        Uuid(as_uuid=True), nullable=True, unique=True, comment='연결된 포트')
    fixed_address: str = Column(String(15), comment='고정 ip 주소')
    created_at: datetime = Column(DateTime, comment='생성시간')
    updated_at: datetime = Column(DateTime, comment='수정시간')
    deleted_at: datetime = Column(DateTime, nullable=True, comment='삭제시간')

    volumes: Mapped[List[Volume]] = relationship(
        'Volume', back_populates='server')
    floatingip: Mapped['Floatingip'] = relationship(
        'Floatingip', back_populates='server')

    @property
    def deleted(self) -> bool:
        return self.deleted_at is not None
