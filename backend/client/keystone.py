from backend.client.base import BaseClient
from backend.schema.oa_base import OpenstackBaseRequest
from backend.schema.auth import TokenCreateRequest, TokenDto


class KeystoneClient(BaseClient):
    """
    인증 api와 관련한 클래스
    """

    def __init__(self) -> None:
        super().__init__('/identity/v3')

    async def password_authentication_with_unscoped_authorization(self,
                                                                  tokenCreateRequest: TokenCreateRequest) -> TokenDto:
        """
        로그인을 요청하고, 비정상의 경우 오류를 raise한다
        [POST] /identity/v3/auth/tokens
        - 201 : 로그인 성공
        - 400 : 필드 오류
        - 401 : 로그인 오류
        """
        oa_request = OpenstackBaseRequest(
            url=self.COMPONENT_URL+'/auth/tokens', headers={'Content-Type': 'application/json'}, data=tokenCreateRequest.serialize())
        oa_response = await self.request_openstack('POST', oa_request)
        return TokenDto.deserialize(oa_response)


