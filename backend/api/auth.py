from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from backend.core.dependency import get_token_or_raise
from backend.schema.auth import TokenCreateRequest
from backend.service.auth import AuthService
from backend.util.constant import USER_TOKEN_HEADER_FIELD, RESPONSE_LOGIN_SUCCESS, RESPONSE_LOGOUT_SUCCESS

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login/")
async def login(tokenCreateRequest: TokenCreateRequest, service: AuthService = Depends()):
    tokenDto = await service.login(tokenCreateRequest)
    response = JSONResponse(status_code=status.HTTP_200_OK, content=RESPONSE_LOGIN_SUCCESS)
    response.set_cookie(USER_TOKEN_HEADER_FIELD, tokenDto.token, httponly=True,
                        expires=tokenDto.expires_at)
    return response


@router.post("/logout/")
async def logout(token: str = Depends(get_token_or_raise)):
    response = JSONResponse(status_code=status.HTTP_200_OK, content=RESPONSE_LOGOUT_SUCCESS)
    response.delete_cookie(USER_TOKEN_HEADER_FIELD)
    return response
