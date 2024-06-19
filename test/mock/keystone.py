from datetime import datetime, timedelta, timezone

from backend.client.keystone import KeystoneClient
from backend.schema.oa_base import OpenstackBaseResponse
from backend.core.exception import OpenstackClientException
from backend.schema.auth import TokenCreateRequest, TokenDto
from test.conftest import generate_string


class KeystoneClientMock(KeystoneClient):

    def __init__(self) -> None:
        super().__init__()

    async def password_authentication_with_unscoped_authorization_success(self,
                                                                          tokenCreateRequest: TokenCreateRequest) -> TokenDto:
        """
        로그인 성공 -> 한시간 유효한 토큰을 발급
        """
        expires_at = datetime.now() + timedelta(hours=1)
        expires_at = expires_at.astimezone(timezone.utc)
        return TokenDto(username=tokenCreateRequest.username, token=generate_string(183),
                        expires_at=expires_at)

    async def password_authentication_with_unscoped_authorization_401(self, tokenCreateRequest: TokenCreateRequest):
        """
        로그인 실패
        """
        oa_response = OpenstackBaseResponse(status=401, headers={}, data={
            "error": {
                "code": 401,
                "message": "The request you have made requires authentication.",
                "title": "Unauthorized"
            }
        })
        raise OpenstackClientException(oa_response)

    async def password_authentication_with_unscoped_authorization_400(self, tokenCreateRequest: TokenCreateRequest):
        """
        필드 조건 오류
        """
        oa_response = OpenstackBaseResponse(status=400, data={
            "error": {
                "code": 400,
                "message": "Expecting to find passwords in identity. The server could not comply with the request since it is either malformed or otherwise incorrect. The client is assumed to be in error.",
                "title": "Bad Request"
            }
        })
        raise OpenstackClientException(oa_response)


keystone_client = KeystoneClient()
