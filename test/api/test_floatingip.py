import uuid
from uuid import UUID
import httpx
import pytest
from pytest_mock import MockFixture
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.client import NovaClient
from backend.client.neutron import NeutronClient
from backend.core.config import get_setting
from backend.core.exception_handler import ErrorContent
from backend.model.floatingip import Floatingip
from backend.model.server import Server, ServerStatus
from backend.schema.floatingip import FloatingipRemainLimitDto
from backend.schema.response import FloatingipResponse
from backend.schema.server import ServerDto
from backend.util.constant import (ERR_FLOATINGIP_NOT_FOUND, ERR_FLOATINGIP_PORT_CONFLICT,
                                   ERR_FLOATINGIP_STATUS_CONFLICT, ERR_SERVER_STATUS_CONFLICT,
                                   ERR_FLOATINGIP_LIMIT_OVER)
from test.conftest import generate_string, test_db_session
from test.mock.neutron import NeutronClientMock
from test.mock.response import FloatingipResponseMock

SETTINGS = get_setting()


@pytest.mark.asyncio
async def test_floatingip_list_basic(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession,
                                     mocker: MockFixture):
    """
    test floatingip list api
    * 200 : 성공
    """
    # given
    floatingips = await test_db_session.scalars(select(Floatingip).offset(0).limit(10))
    expected_response = await FloatingipResponseMock.mapper(el=list(floatingips))
    mocker.patch.object(FloatingipResponse, 'mapper', FloatingipResponseMock.mapper)
    # when
    response = await test_client_no_token.get("/api/floatingips/")

    # then
    assert response.status_code == 200
    assert response.json() == [el.model_dump(mode='json') for el in expected_response]


@pytest.mark.asyncio
async def test_floatingip_get_basic(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession,
                                    basic_floatingip: Floatingip, mocker: MockFixture):
    """
    test floatingip get api
    * 200 : 성공
    """
    # given
    cur_floatingip = basic_floatingip
    floatingip = await test_db_session.scalar(
        select(Floatingip).filter(Floatingip.floatingip_id == cur_floatingip.floatingip_id))
    expected_response = (await FloatingipResponseMock.mapper(floatingip)).model_dump(mode='json')
    mocker.patch.object(FloatingipResponse, 'mapper', FloatingipResponseMock.mapper)
    # when
    response = await test_client_no_token.get(f"/api/floatingips/{cur_floatingip.floatingip_id}/")
    # then
    assert response.status_code == 200
    assert response.json() == expected_response


@pytest.mark.asyncio
async def test_floatingip_get_not_found(test_client_no_token: httpx.AsyncClient):
    """
    test floatingip get api
    * 404 : not found
    """
    # given
    id = uuid.uuid4()
    response = await test_client_no_token.get(f"/api/floatingips/{id}/")
    # then
    assert response.status_code == 404
    assert response.json() == ErrorContent(error_type='error', message=ERR_FLOATINGIP_NOT_FOUND,
                                           detail=f'floatingip (id :{id}) not found').__dict__


@pytest.mark.asyncio
async def test_floatingip_create_success(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                         test_db_session: AsyncSession):
    """
    test create floatingip api
    * 201 : 생성 성공
    """
    # given
    mocker.patch.object(NeutronClient, 'create_floating_ip', NeutronClientMock.create_floating_ip_success)
    floatingip_create_request = {'description': 'test floatingip create success'}
    # given [MOCK] response
    mocker.patch.object(FloatingipResponse, 'mapper', FloatingipResponseMock.mapper)
    # given [MOCK] NEUTRON check quota : 10개 남음
    mocker.patch.object(NeutronClient, 'show_quota_details_for_tenant',
                        return_value=FloatingipRemainLimitDto(remain_cnt=10))
    # when
    response = await test_client_no_token.post("/api/floatingips/", json=floatingip_create_request)
    # then
    assert response.status_code == 201
    # check db with response
    floatingip_id = response.json()['floatingip_id']
    floatingip = await test_db_session.scalar(
        select(Floatingip).filter(Floatingip.floatingip_id == UUID(floatingip_id)))
    assert response.json() == (await FloatingipResponseMock.mapper(el=floatingip)).model_dump(mode='json')


@pytest.mark.asyncio
async def test_floatingip_create_no_description(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession,
                                                mocker: MockFixture):
    """
    test create floatingip api
    * 201 : 생성 성공
        - description 없는 경우, 빈 문자열로 초기화
    """
    # given
    mocker.patch.object(NeutronClient, 'create_floating_ip', NeutronClientMock.create_floating_ip_success)
    empty_request = {}
    # given [MOCK] response
    mocker.patch.object(FloatingipResponse, 'mapper', FloatingipResponseMock.mapper)
    # given [MOCK] NEUTRON check quota : 10개 남음
    mocker.patch.object(NeutronClient, 'show_quota_details_for_tenant',
                        return_value=FloatingipRemainLimitDto(remain_cnt=10))

    # when
    response = await test_client_no_token.post("/api/floatingips/", json=empty_request)
    # then
    assert response.status_code == 201
    # check db with response
    floatingip_id = response.json()['floatingip_id']
    floatingip = await test_db_session.scalar(
        select(Floatingip).filter(Floatingip.floatingip_id == UUID(floatingip_id)))
    assert response.json() == (await FloatingipResponseMock.mapper(floatingip)).model_dump(mode='json')


@pytest.mark.asyncio
async def test_floatingip_create_long_description(test_client_no_token: httpx.AsyncClient,
                                                  test_db_session: AsyncSession):
    """
    test create floatingip api
    * 400 : 필드 조건 오류
        - description 255자 이상인 경우
    """
    # given
    invalid_request = {'description': generate_string(256)}
    # when
    response = await test_client_no_token.post("/api/floatingips/", json=invalid_request)
    # then
    assert response.status_code == 400
    assert response.json() == ErrorContent(error_type='string_too_long',
                                           message='String should have at most 255 characters',
                                           detail={'input': invalid_request['description'],
                                                   'loc': ['body', 'description']}).__dict__


@pytest.mark.asyncio
async def test_floatingip_create_no_available(test_client_no_token: httpx.AsyncClient,
                                              mocker: MockFixture):
    """
    test create floatingip api
    * 409 : 가용 공간 없는 경우
    """
    # given
    request = {'description': generate_string(10)}

    # given [MOCK] NEUTRON check quota : 0개 남음
    mocker.patch.object(NeutronClient, 'show_quota_details_for_tenant',
                        return_value=FloatingipRemainLimitDto(remain_cnt=0))
    # when
    response = await test_client_no_token.post("/api/floatingips/", json=request)
    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error',
                                           message=ERR_FLOATINGIP_LIMIT_OVER, detail='').__dict__


@pytest.mark.asyncio
async def test_floatingip_update_success(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                         basic_floatingip: Floatingip):
    """
    test update floatingip description api
    * 200 : description 업데이트 성공
    """
    # given
    cur_floatingip = basic_floatingip
    update_request = {'description': generate_string(20)}
    cur_floatingip.description = update_request['description']
    mocker.patch.object(FloatingipResponse, 'mapper', FloatingipResponseMock.mapper)
    mocked_update_client_response = NeutronClientMock.update_floating_ip_success(floatingip=cur_floatingip)
    mocker.patch.object(
        NeutronClient, 'update_floating_ip',
        return_value=mocked_update_client_response
    )

    # when
    response = await test_client_no_token.patch(f"/api/floatingips/{cur_floatingip.floatingip_id}/",
                                                json=update_request)

    # then
    assert response.status_code == 200
    assert response.json() == (await FloatingipResponseMock.mapper(cur_floatingip)).model_dump(mode='json')


@pytest.mark.asyncio
async def test_floatingip_update_long_description(test_client_no_token: httpx.AsyncClient,
                                                  basic_floatingip: Floatingip):
    """
    test update floatingip description api
    * 400 : description 255자 넘어가는 경우
    """
    # given
    cur_floatingip = basic_floatingip
    invalid_request = {'description': generate_string(256)}

    # when
    response = await test_client_no_token.patch(f"/api/floatingips/{cur_floatingip.floatingip_id}/",
                                                json=invalid_request)

    # then
    assert response.status_code == 400
    assert response.json() == ErrorContent(error_type='string_too_long',
                                           message='String should have at most 255 characters',
                                           detail={'input': invalid_request['description'],
                                                   'loc': ['body', 'description']}).__dict__


@pytest.mark.asyncio
async def test_floatingip_delete_success(test_client_no_token: httpx.AsyncClient,
                                         basic_floatingip: Floatingip,
                                         mocker: MockFixture,
                                         test_db_session: AsyncSession):
    """
    test delete floatingip api
    * 204 : 포트 연결되어 있지 않은 경우 삭제 가능, db soft delete도 검증
    """
    # given
    cur_floatingip = basic_floatingip
    mocker.patch.object(NeutronClient, 'delete_floating_ip', NeutronClientMock.delete_floating_ip_success)
    # when
    response = await test_client_no_token.delete(f"/api/floatingips/{cur_floatingip.floatingip_id}/")
    # then
    assert response.status_code == 204
    # then test actual db
    actual_floatingip = await test_db_session.scalar(
        select(Floatingip).filter(Floatingip.floatingip_id == cur_floatingip.floatingip_id))
    assert actual_floatingip is not None  # soft delete
    assert actual_floatingip.deleted is True


@pytest.mark.asyncio
async def test_floatingip_delete_conflict(test_client_no_token: httpx.AsyncClient,
                                          basic_floatingip_with_server: (Floatingip, Server),
                                          test_db_session: AsyncSession):
    """
    test delete floatingip api
    * 409 : 이미 포트와 연결되어 있는 경우 충돌
    """
    # given
    cur_floatingip, _ = basic_floatingip_with_server
    # when
    response = await test_client_no_token.delete(f"/api/floatingips/{cur_floatingip.floatingip_id}/")
    # then test response
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_FLOATINGIP_PORT_CONFLICT, detail='').__dict__
    # then test actual db
    actual_floatingip = await test_db_session.scalar(
        select(Floatingip).filter(Floatingip.floatingip_id == cur_floatingip.floatingip_id))
    assert actual_floatingip.deleted is False


@pytest.mark.asyncio
async def test_floatingip_delete_already_deleted(test_client_no_token: httpx.AsyncClient,
                                                 deleted_floatingip: Floatingip):
    """
    test delete floatingip api
    * 409 : 이미 삭제된 floatingip의 경우 불가능
    """
    # given
    cur_floatingip = deleted_floatingip
    # when
    response = await test_client_no_token.delete(f"/api/floatingips/{cur_floatingip.floatingip_id}/")
    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_FLOATINGIP_STATUS_CONFLICT,
                                           detail='').__dict__


@pytest.mark.asyncio
async def test_floatingip_attach_port_success(test_client_no_token: httpx.AsyncClient,
                                              test_db_session: AsyncSession,
                                              mocker: MockFixture,
                                              basic_floatingip: Floatingip,
                                              basic_server_with_port: Server):
    """
    test attach port of floatingip api
    * 202 : basic_floatingip와 basic_server가 연결 성공
    """
    # given
    cur_floatingip = basic_floatingip
    request = {"port_id": f"{basic_server_with_port.fk_port_id}"}
    cur_floatingip.fk_port_id = basic_server_with_port.fk_port_id  # port id 업데이트
    # given mocked neutron_client
    mocked_update_client_response = NeutronClientMock.update_floating_ip_success(floatingip=cur_floatingip)
    mocker.patch.object(NeutronClient, 'update_floating_ip', return_value=mocked_update_client_response)
    mocker.patch.object(NovaClient, 'show_server_details',
                        return_value=ServerDto(**basic_server_with_port.__dict__, status=ServerStatus.ACTIVE))
    mocker.patch.object(FloatingipResponse, 'mapper', FloatingipResponseMock.mapper)

    # when
    response = await test_client_no_token.patch(f"/api/floatingips/{cur_floatingip.floatingip_id}/ports/", json=request)

    # then test response
    assert response.status_code == 202
    assert response.json() == (await FloatingipResponseMock.mapper(cur_floatingip)).model_dump(mode='json')


@pytest.mark.asyncio
async def test_floatingip_detach_port_success(test_client_no_token: httpx.AsyncClient,
                                              test_db_session: AsyncSession,
                                              mocker: MockFixture,
                                              basic_floatingip_with_server: (Floatingip, Server),
                                              ):
    """
    test detach port of floatingip api
    * 202 : basic_floatingip와 basic_server가 해제 성공
    * task : 연결 요청이 완료되고, status가 DOWN으로 변경됨
    """
    # given
    cur_floatingip, _ = basic_floatingip_with_server
    request = {"port_id": None}
    # given mock neutron_client
    cur_floatingip.fk_port_id = None
    mocked_update_client_response = NeutronClientMock.update_floating_ip_success(floatingip=cur_floatingip)
    mocker.patch.object(FloatingipResponse, 'mapper', FloatingipResponseMock.mapper)
    # given mock task
    mocker.patch.object(NeutronClient, 'update_floating_ip', return_value=mocked_update_client_response)

    # when
    response = await test_client_no_token.patch(f"/api/floatingips/{cur_floatingip.floatingip_id}/ports/", json=request)

    # then
    assert response.status_code == 202
    assert response.json() == (await FloatingipResponseMock.mapper(cur_floatingip)).model_dump(mode='json')


@pytest.mark.asyncio
async def test_floatingip_attach_port_server_status(test_client_no_token: httpx.AsyncClient,
                                                    basic_floatingip: Floatingip,
                                                    basic_server_with_port: Server,
                                                    mocker: MockFixture
                                                    ):
    """
    test attach port of floatingip api
    * 409 : server의 상태가 ACTIVE가 아닌 경우
    """
    # given
    cur_floatingip = basic_floatingip
    request = {'port_id': str(basic_server_with_port.fk_port_id)}
    mocker.patch.object(NovaClient, 'show_server_details',
                        return_value=ServerDto(**basic_server_with_port.__dict__, status=ServerStatus.ERROR))
    # when
    response = await test_client_no_token.patch(f"/api/floatingips/{cur_floatingip.floatingip_id}/ports/", json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_SERVER_STATUS_CONFLICT,
                                           detail=f'current server status : {ServerStatus.ERROR.value}').__dict__
