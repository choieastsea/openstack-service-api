import pytest
import httpx
from pytest_mock import MockFixture

from backend.client.keystone import KeystoneClient
from test.conftest import SETTINGS
from backend.util.constant import (RESPONSE_LOGIN_SUCCESS, RESPONSE_LOGOUT_SUCCESS, USER_TOKEN_HEADER_FIELD,
                                   ERR_NO_TOKEN_IN_HEADER)
from backend.core.exception_handler import ErrorContent
from test.mock.keystone import KeystoneClientMock


@pytest.mark.asyncio
async def test_login_success(test_client: httpx.AsyncClient, mocker: MockFixture):
    """
    test login api
    * 200 : 로그인 성공
    """
    # given
    mocker.patch.object(KeystoneClient, 'password_authentication_with_unscoped_authorization',
                        KeystoneClientMock.password_authentication_with_unscoped_authorization_success)
    login_data = {"username": SETTINGS.OPENSTACK_USERNAME, "password": SETTINGS.OPENSTACK_PASSWORD}

    # when
    response = await test_client.post("/api/auth/login/", json=login_data)

    # then
    assert response.status_code == 200
    assert response.json() == RESPONSE_LOGIN_SUCCESS
    # 올바른 필드 네임으로 set-cookie가 실행되는지 검증
    assert response.cookies.get(USER_TOKEN_HEADER_FIELD) is not None


@pytest.mark.asyncio
async def test_login_validation(test_client: httpx.AsyncClient):
    """
    test login api
    * 400 : 옳지 않은 field 정보
    """
    # given
    invalid_login_data = {"username": SETTINGS.OPENSTACK_USERNAME}
    # when
    response = await test_client.post("/api/auth/login/", json=invalid_login_data)
    # then
    assert response.status_code == 400
    assert response.json() == ErrorContent(error_type='missing', message='Field required',
                                           detail={'input': {'username': SETTINGS.OPENSTACK_USERNAME},
                                                   'loc': ['body', 'password']}).__dict__


@pytest.mark.asyncio
async def test_login_failed(test_client: httpx.AsyncClient, mocker: MockFixture):
    """
    test login api
    * 401 : 로그인 실패
    """
    # given
    mocker.patch.object(KeystoneClient, 'password_authentication_with_unscoped_authorization',
                        KeystoneClientMock.password_authentication_with_unscoped_authorization_401)
    login_data = {"username": SETTINGS.OPENSTACK_USERNAME, "password": "WRONG_PASSWORD"}
    # when
    response = await test_client.post("/api/auth/login/", json=login_data)
    # then
    assert response.status_code == 401
    assert response.json() == ErrorContent(error_type='error',
                                           message='The request you have made requires authentication.',
                                           detail='').__dict__


@pytest.mark.asyncio
async def test_login_error(test_client: httpx.AsyncClient, mocker: MockFixture):
    """
    test login api
    * 500 : openstack에서 400 에러 발생하는 경우
    """
    # given
    mocker.patch.object(KeystoneClient, 'password_authentication_with_unscoped_authorization',
                        KeystoneClientMock.password_authentication_with_unscoped_authorization_400)
    login_data = {"username": SETTINGS.OPENSTACK_USERNAME, "password": SETTINGS.OPENSTACK_PASSWORD}
    # when
    response = await test_client.post("/api/auth/login/", json=login_data)
    # then
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_logout_success(test_client: httpx.AsyncClient):
    """
    test logout api
    * 200 : 로그아웃 성공
    쿠키에 token 실어서 보내야 하며, 로그아웃 이후에는 지워져야함
    """
    # given
    cookies = {USER_TOKEN_HEADER_FIELD: 'token value'}
    # when
    response = await test_client.post("/api/auth/logout/", cookies=cookies)
    # then
    assert response.status_code == 200
    assert response.json() == RESPONSE_LOGOUT_SUCCESS
    assert response.cookies.get(USER_TOKEN_HEADER_FIELD) is None


@pytest.mark.asyncio
async def test_logout_no_token(test_client: httpx.AsyncClient):
    """
    test logout api
    * 401 : 쿠키의 토큰이 없는 경우
    """
    # given
    cookies = {}
    # when
    response = await test_client.post("/api/auth/logout/", cookies=cookies)
    # then
    assert response.status_code == 401
    assert response.json() == ErrorContent(error_type='error', message=ERR_NO_TOKEN_IN_HEADER, detail='').__dict__
