import enum
from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, Uuid, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.core.db import Base


class VolumeStatus(str, enum.Enum):
    CREATING = 'creating'
    AVAILABLE = 'available'
    RESERVED = 'reserved'
    ATTACHING = 'attaching'
    DETACHING = 'detaching'
    IN_USE = 'in-use'
    MAINTENANCE = 'maintenance'
    DELETING = 'deleting'
    AWAITING_TRANSFER = 'awaiting-transfer'
    ERROR = 'error'
    ERROR_DELETING = 'error_deleting'
    BACKING_UP = 'backing-up'
    RESTORING_BACKUP = 'restoring-backup'
    ERROR_BACKING_UP = 'error_backing-up'
    ERROR_RESTORING = 'error_restoring'
    ERROR_EXTENDING = 'error_extending'
    DOWNLOADING = 'downloading'
    UPLOADING = 'uploading'
    RETYPING = 'retyping'
    EXTENDING = 'extending'

    # 추가
    DELETED = 'deleted'


class Volume(Base):
    __tablename__ = 'volume'
    volume_id: UUID = Column(
        Uuid(as_uuid=True), primary_key=True, comment='volume id')
    name: str = Column(String(255), comment='volume name')
    description: str = Column(String(255), comment='volume description')
    volume_type: str = Column(String(12), comment='volume type (lvmdriver-1)')
    size: int = Column(Integer, comment='volume 용량')
    fk_server_id: UUID = Column(Uuid(as_uuid=True), ForeignKey(
        'server.server_id'), nullable=True)
    fk_project_id: UUID = Column(Uuid(as_uuid=True))
    fk_image_id: UUID = Column(Uuid(as_uuid=True), comment='image id')
    created_at: datetime = Column(DateTime, comment='생성시간')
    # cinder에서는 기본적으로 생성시 updated_at : null
    updated_at: datetime = Column(DateTime, comment='수정시간')
    deleted_at: datetime = Column(DateTime, nullable=True, comment='삭제시간')

    server = relationship('Server', back_populates='volumes')

    @property
    def is_root_volume(self) -> bool:
        # image로부터 만들어졌고 연결된 서버 있다면 root volume으로 간주
        return self.fk_image_id is not None and self.fk_server_id is not None

    @property
    def deleted(self):
        return self.deleted_at is not None
