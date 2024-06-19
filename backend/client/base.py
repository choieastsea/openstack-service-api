import logging
from aiohttp import ClientSession
from typing import Optional

from backend.util.constant import ERR_TOKEN_INVALID
from backend.core.config import get_setting
from backend.core.exception import OpenstackClientException, ApiServerException
from backend.schema.oa_base import OpenstackBaseResponse, OpenstackBaseRequest

SETTINGS = get_setting()
logger = logging.getLogger(__name__)


class BaseClient:
    """
    Openstack api와 통신하기 위한 상위 클래스
    하위 클래스를 통하여 service layer에서 request_openstack로 통신 가능하다
    """

    def __init__(self, component_url: str = '') -> None:
        """
        - component_url : 오픈스택 컴포넌트의 url 
        """
        self.COMPONENT_URL = component_url

    async def request_openstack(self, method: str, request: OpenstackBaseRequest,
                                port: Optional[int] = None) -> OpenstackBaseResponse:
        """
        request를 실행하고 결과를 mapping하여 리턴한다
        만약 2XX 응답코드가 아닌 경우, OpenstackClientException을 발생시킨다
        이후 client session을 종료한다
        """
        async with ClientSession(
                base_url=SETTINGS.OPENSTACK_ROOT_URL if not port else f'{SETTINGS.OPENSTACK_ROOT_URL}:{port}') as session:
            async with session.request(method, request.url, headers=request.headers, data=request.data) as resp:
                oa_response = await OpenstackBaseResponse.mapper(resp)
                logger.info(
                    f'({oa_response.status}) URL:{request.url}, '
                    f'DATA:{request.data if request.data else ""},'
                    f'HEADERS:{request.headers if request.headers else ""},'
                    f'RESPONSE:{oa_response.data}')
                if oa_response.status < 200 or oa_response.status >= 300:
                    if oa_response.status == 401:
                        # 토큰은 있지만, openstack에서 401 응답한 경우
                        raise ApiServerException(
                            status=401,
                            message=ERR_TOKEN_INVALID
                        )
                    raise OpenstackClientException(oa_response)
                return oa_response
