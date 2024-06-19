from pydantic import BaseModel
import json
from datetime import datetime

from backend.schema.oa_base import OpenstackBaseResponse
from backend.util.constant import OA_TOKEN_LOGIN_HEADER_FIELD


class TokenCreateRequest(BaseModel):
    """
    사용자가 보낼 login request
    """
    username: str
    password: str

    def serialize(self) -> str:
        """
        openstack api에 보낼 login request(json)로 변환
        """
        return json.dumps({
            "auth": {
                "identity": {
                    "methods": [
                        "password"
                    ],
                    "password": {
                        "user": {
                            "name": self.username,
                            "domain": {
                                "name": "Default"
                            },
                            "password": self.password
                        }
                    }
                }
            }
        })


class TokenDto(BaseModel):
    username: str
    token: str
    expires_at: datetime

    @staticmethod
    def deserialize(oa_response: OpenstackBaseResponse) -> 'TokenDto':
        token = oa_response.headers[OA_TOKEN_LOGIN_HEADER_FIELD]
        username = oa_response.data['token']['user']['name']
        expires_at = datetime.fromisoformat(
            oa_response.data['token']['expires_at'])  # pydantic 기본 변환시 , response.set_cookie에서 type 충돌이 발생
        return TokenDto(username=username, token=token, expires_at=expires_at)
