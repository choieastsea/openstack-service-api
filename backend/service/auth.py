from backend.client import keystone_client
from backend.schema.auth import TokenCreateRequest, TokenDto


class AuthService:
    def __init__(self):
        pass

    async def login(self, tokenCreateRequest: TokenCreateRequest) -> TokenDto:
        return await keystone_client.password_authentication_with_unscoped_authorization(tokenCreateRequest)
