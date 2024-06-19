from pydantic import BaseModel, Field
from aiohttp import ClientResponse
from typing import Optional

class OpenstackBaseRequest(BaseModel):
    """
    Openstack API에 요청을 보내기 위한 형식
    - url : sub-url
    - headers : dict 형식의 헤더
    - data : serialized request body
    """
    url: str
    headers: dict = None
    data: str = None


class OpenstackBaseResponse(BaseModel):
    """
    Openstack API에 응답을 받기 위한 형식
    - status : HTTP status
    - headers : dict 형식의 헤더
    - data : dict 형식의 response body
    """
    status: int
    headers: Optional[dict] = Field(None)
    data: Optional[dict] = Field(None)

    @staticmethod
    async def mapper(response: ClientResponse):
        """
        ClientResponse(aiohttp의 응답 결과)를 OpenstackBaseResponse로 변환
        """
        return OpenstackBaseResponse(status=response.status, headers=response.headers,
                                     data=await response.json() if response.content_type == 'application/json' else None)
