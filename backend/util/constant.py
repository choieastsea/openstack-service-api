from typing import Final

USER_TOKEN_HEADER_FIELD: Final[str] = 'token'
OA_TOKEN_LOGIN_HEADER_FIELD: Final[str] = 'X-Subject-Token'
OA_TOKEN_HEADER_FIELD: Final[str] = 'X-Auth-Token'

# RESPSNSE STRING
RESPONSE_LOGIN_SUCCESS: Final[str] = '로그인 성공'
RESPONSE_LOGOUT_SUCCESS: Final[str] = '로그아웃 성공'

# ERROR STRING
ERR_NO_TOKEN_IN_HEADER: Final[str] = '요청 헤더에 토큰이 존재하지 않습니다'
ERR_TOKEN_INVALID: Final[str] = '해당 토큰이 유효하지 않습니다'
ERR_FLOATINGIP_NOT_FOUND: Final[str] = '해당하는 id의 floating ip가 존재하지 않습니다'
ERR_FLOATINGIP_LIMIT_OVER: Final[str] = '남아있는 floating ip 할당량이 없습니다'
ERR_FLOATINGIP_STATUS_CONFLICT: Final[str] = ' floating ip가 요청을 수행할 수 있는 상태가 아닙니다'
ERR_FLOATINGIP_PORT_CONFLICT: Final[str] = '서버와 연결되어 있으므로 floating ip의 삭제가 불가합니다'

ERR_SERVER_NOT_FOUND: Final[str] = '해당하는 id의 server가 존재하지 않습니다'
ERR_SERVER_PORT_NOT_FOUND: Final[str] = '해당 포트의 server가 존재하지 않습니다'
ERR_SERVER_STATUS_CONFLICT: Final[str] = '현재 서버 상태로 인하여 요청을 수행할 수 없습니다'
ERR_SERVER_NAME_DUPLICATED: Final[str] = '해당 서버 이름이 이미 존재합니다'
ERR_SERVER_ALREADY_DELETED: Final[str] = '해당 서버는 이미 삭제되었습니다'
ERR_SERVER_VOLUME_NOT_CONNECTED: Final[str] = '해당 서버와 볼륨은 연결되어 있지 않습니다'
ERR_SERVER_ROOT_VOLUME_CANT_DETACH: Final[str] = '서버의 루트 볼륨은 연결 해제할 수 없습니다'
ERR_SERVER_LIMIT_OVER: Final[str] = '남아있는 서버 할당량이 없습니다'

ERR_FLAVOR_NOT_FOUND: Final[str] = '해당하는 flavor가 존재하지 않습니다'
ERR_IMAGE_NOT_FOUND: Final[str] = '해당하는 image가 존재하지 않습니다'
ERR_IMAGE_SIZE_CONFLICT: Final[str] = '요청한 volume의 사이즈는 image의 가상 사이즈보다 커야합니다'

ERR_VOLUME_NAME_DUPLICATED: Final[str] = '해당 볼륨 이름이 이미 존재합니다'
ERR_VOLUME_LIMIT_OVER: Final[str] = '남아있는 볼륨 할당량이 없습니다'
ERR_VOLUME_NOT_FOUND: Final[str] = '해당하는 볼륨이 존재하지 않습니다'
ERR_VOLUME_ALREADY_DELETED: Final[str] = '해당 볼륨은 이미 삭제되었습니다'
ERR_VOLUME_SERVER_CONFLICT: Final[str] = '서버와 연결되어 있으므로 볼륨의 삭제가 불가합니다'
ERR_VOLUME_STATUS_CONFLICT: Final[str] = '해당 볼륨이 요청을 수행할 수 있는 상태가 아닙니다'
ERR_VOLUME_SIZE_UPGRADE_CONFLICT: Final[str] = '볼륨의 크기는 현재 볼륨보다 크게만 가능합니다'
