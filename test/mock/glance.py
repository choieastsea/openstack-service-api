from uuid import UUID

from backend.client.glance import GlanceClient
from backend.core.exception import OpenstackClientException
from backend.schema.oa_base import OpenstackBaseResponse
from backend.schema.server import ImageDto


class GlanceClientMock(GlanceClient):
    def __init__(self) -> None:
        super().__init__()

    async def show_image_success(self, image_id: UUID, token: str):
        return ImageDto(id=image_id, status='', virtual_size=1)

    async def show_image_not_found(self, image_id: UUID, token: str):
        oa_response = OpenstackBaseResponse(status=404, headers={}, data={})
        raise OpenstackClientException(oa_response)

    async def show_image_larger_than_1(self, image_id: UUID, token: str):
        image_data = {
            "id": "671b2bd4-af99-4c5c-bcb0-618d12b732d7",
            "name": "centos7-nginx",
            "disk_format": "qcow2",
            "status": "active",
            "min_ram": 0,
            "min_disk": 0,
            "size": 2474442752,
            "virtual_size": 32212254720,
        }
        oa_response = OpenstackBaseResponse(status=200, headers={}, data=image_data)
        return ImageDto.deserialize(oa_response, many=False)


glance_client_mock = GlanceClientMock()
