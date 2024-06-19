from datetime import datetime
from uuid import UUID

from backend.client import CinderClient
from backend.core.config import get_setting
from backend.core.exception import OpenstackClientException
from backend.model.volume import VolumeStatus, Volume
from backend.schema.oa_base import OpenstackBaseResponse
from backend.schema.volume import VolumeDto

SETTINGS = get_setting()


class CinderClientMock(CinderClient):
    def __init__(self) -> None:
        super().__init__()

    def update_a_volume_failed(self):
        raise OpenstackClientException(OpenstackBaseResponse(status=500))

    @staticmethod
    def update_volume_success(volume: Volume, request: dict):
        volume.name = request['name']
        volume.description = request['description']

        return VolumeDto(
            **volume.__dict__,
            status=VolumeStatus.AVAILABLE
        )

    @staticmethod
    def create_volume_success(volume_id: UUID, request: dict):
        """
        빈 볼륨 생성 성공
        """
        volume_response = request
        return VolumeDto(
            volume_id=volume_id,
            name=volume_response['name'],
            description=volume_response['description'],
            volume_type=SETTINGS.OPENSTACK_DEFAULT_VOLUME_TYPE,
            size=volume_response['size'],
            fk_server_id=None,
            fk_project_id=UUID(SETTINGS.OPENSTACK_PROJECT_ID),
            fk_image_id=None,
            status=VolumeStatus.CREATING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            deleted_at=None
        )

    @staticmethod
    def show_volume_detail_with_status(volume: Volume, status: VolumeStatus) -> VolumeDto:
        """
        해당 status를 갖는 volumedto 리턴
        """
        return VolumeDto(**volume.__dict__, status=status)


cinder_client_mock = CinderClientMock()
