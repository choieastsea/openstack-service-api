from typing import List

from backend.client import nova_client
from backend.schema.server import FlavorDto


class FlavorService:
    async def get_flavors(self, token: str) -> List[FlavorDto]:
        """
        flavor list를 반환
        :param token: 인증토큰
        :return: List[FlavorDto]
        """
        return await nova_client.list_flavors_with_details(token)
