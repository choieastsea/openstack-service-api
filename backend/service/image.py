from typing import List

from backend.client import glance_client
from backend.schema.server import ImageDto


class ImageService:
    async def get_images(self, token: str) -> List[ImageDto]:
        """
        image list를 반환
        :param token: 인증토큰
        :return: List[ImageDto]
        """
        return await glance_client.list_images(token)
