from typing import List
from uuid import UUID

from backend.client.base import BaseClient
from backend.core.config import get_setting
from backend.schema.oa_base import OpenstackBaseRequest
from backend.schema.server import ImageDto
from backend.util.constant import OA_TOKEN_HEADER_FIELD

SETTINGS = get_setting()


class GlanceClient(BaseClient):
    """
    image api와 관련한 클래스
    """

    def __init__(self) -> None:
        super().__init__(f'/image/v2')

    async def list_images(self, token: str) -> List[ImageDto]:
        """
        200: 요청 성공
        """
        oa_request = OpenstackBaseRequest(url=f'{self.COMPONENT_URL}/images',
                                          headers={OA_TOKEN_HEADER_FIELD: token})
        oa_response = await self.request_openstack(method='GET', request=oa_request)

        return ImageDto.deserialize(oa_response, many=True)

    async def show_image(self, image_id: UUID, token: str) -> ImageDto:
        """
        200: 조회 성공
        """
        oa_request = OpenstackBaseRequest(url=f'{self.COMPONENT_URL}/images/{image_id}',
                                          headers={OA_TOKEN_HEADER_FIELD: token})
        oa_response = await self.request_openstack(method='GET', request=oa_request)

        return ImageDto.deserialize(oa_response, many=False)


