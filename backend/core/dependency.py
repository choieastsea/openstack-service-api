from fastapi import Request, status

from backend.util.constant import USER_TOKEN_HEADER_FIELD, ERR_NO_TOKEN_IN_HEADER
from backend.core.exception import ApiServerException


def get_token_or_raise(request: Request):
    """
    'token' field로 존재하는 cookie의 데이터를 가져오고, 없다면 401 raise
    - 인증이 필요한 api의 경우, depends의 인자로 해당 함수 사용 
    """
    token = request.cookies.get(USER_TOKEN_HEADER_FIELD)
    if not token:
        raise ApiServerException(
            status=status.HTTP_401_UNAUTHORIZED,
            message=ERR_NO_TOKEN_IN_HEADER
        )
    return token
