import uuid
import httpx
import pytest
from pytest_mock import MockFixture
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_setting
from backend.core.exception_handler import ErrorContent
from backend.model.server import Server, ServerStatus
from backend.model.volume import Volume, VolumeStatus
from backend.schema.response import ServerResponse
from backend.schema.server import ServerUpdateDto, ServerRemainLimitDto
from backend.schema.volume import VolumeRemainLimitDto
from backend.util.constant import (ERR_SERVER_NOT_FOUND, ERR_FLAVOR_NOT_FOUND, ERR_IMAGE_NOT_FOUND,
                                   ERR_IMAGE_SIZE_CONFLICT, ERR_SERVER_NAME_DUPLICATED, ERR_VOLUME_NAME_DUPLICATED,
                                   ERR_SERVER_ALREADY_DELETED,
                                   ERR_VOLUME_NOT_FOUND, ERR_VOLUME_ALREADY_DELETED, ERR_SERVER_ROOT_VOLUME_CANT_DETACH,
                                   ERR_SERVER_VOLUME_NOT_CONNECTED, ERR_SERVER_LIMIT_OVER, ERR_VOLUME_LIMIT_OVER)
from test.conftest import generate_string
from test.mock.cinder import cinder_client_mock
from test.mock.glance import glance_client_mock
from test.mock.nova import nova_client_mock
from test.mock.response import ServerResponseMock
from test.mock.task import task_after_create_server_end_immediately

SETTINGS = get_setting()


@pytest.mark.asyncio
async def test_server_list_basic(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession,
                                 mocker: MockFixture):
    """
    test server list api
    * 200: 성공
    """
    # given
    servers = await test_db_session.scalars(select(Server).offset(0).limit(10))
    expected_response = await ServerResponseMock.mapper(list(servers))
    mocker.patch.object(ServerResponse, 'mapper', ServerResponseMock.mapper)

    # when
    response = await test_client_no_token.get('/api/servers/')
    # then
    assert response.status_code == 200
    assert response.json() == [el.model_dump(mode='json') for el in expected_response]


@pytest.mark.asyncio
async def test_server_get_basic(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession,
                                basic_server: Server, mocker: MockFixture):
    """
    test server get api
    * 200: 성공
    """
    # given
    cur_server = basic_server
    server = await test_db_session.scalar(select(Server).filter(Server.server_id == cur_server.server_id))
    mocker.patch.object(ServerResponse, 'mapper', ServerResponseMock.mapper)

    # when
    response = await test_client_no_token.get(f'/api/servers/{basic_server.server_id}/')
    # then
    assert response.status_code == 200
    assert response.json() == (await ServerResponseMock.mapper(server)).model_dump(mode='json')


@pytest.mark.asyncio
async def test_server_get_not_found(test_client_no_token: httpx.AsyncClient):
    """
    test server get api
    * 404 : not found
    """
    # given
    id = uuid.uuid4()
    response = await test_client_no_token.get(f'/api/servers/{id}/')
    # then
    assert response.status_code == 404
    assert response.json() == ErrorContent(error_type='error', message=ERR_SERVER_NOT_FOUND,
                                           detail=f'server (id: {id}) not found').__dict__


@pytest.mark.asyncio
async def test_server_create_success(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                     test_db_session: AsyncSession):
    """
    test create server api
    * 202 : 성공 및 서버 생성 완료 확인
    """
    # given
    request = {
        "name": "server_created",
        "description": "server created",
        "flavor_id": "1",
        "volume": {
            "name": "volume_name",
            "size": 1,
            "image_id": f"{uuid.uuid4()}"
        }
    }
    server_created_id = uuid.uuid4()
    # given [MOCK] NOVA flavor 검증 통과 (4core, 8GB ram, 16GB disk)
    flavorDto = nova_client_mock.show_flavor_details_basic()
    mocker.patch('backend.service.server.nova_client.show_flavor_details', return_value=flavorDto)
    # given [MOCK] GLANCE image 검증 통과
    mocker.patch('backend.service.server.glance_client.show_image', glance_client_mock.show_image_success)
    # given [MOCK] NOVA quota : 1개 여유, cpu 4개, ram 8GB 여유 (딱 맞게)
    mocker.patch('backend.service.server.nova_client.show_rate_and_absolute_limits',
                 return_value=ServerRemainLimitDto(remain_instances=1, remain_cores=flavorDto.vcpus,
                                                   remain_rams=flavorDto.ram))
    # given [MOCK] CINDER quota 체크 : 1개 여유, disk 16GB 여유
    mocker.patch('backend.service.server.cinder_client.show_absolute_limits_for_project',
                 return_value=VolumeRemainLimitDto(remain_cnt=1, remain_size=flavorDto.disk))
    # given [MOCK] NOVA create server 요청 성공
    mocker.patch('backend.service.server.nova_client.create_server',
                 return_value=nova_client_mock.create_server_success(server_created_id))
    # given [MOCK] NOVA server 정보 요청 성공
    server_created, _ = nova_client_mock.show_server_details_success(server_created_id, request)
    mocker.patch('backend.service.server.nova_client.show_server_details',
                 return_value=server_created)  # 서버 생성 및 확인 완료
    # given [MOCK] background_task 즉시 종료
    mocker.patch('backend.service.server.ServerService._task_after_create_server',
                 callable=task_after_create_server_end_immediately)
    # when
    response = await test_client_no_token.post('/api/servers/', json=request)

    # then
    assert response.status_code == 202

    # then check db
    actual_server = await test_db_session.scalar(select(Server).filter(Server.server_id == server_created.server_id))
    assert (response.json()
            == (await ServerResponseMock.mapper(actual_server, status=ServerStatus.BUILD)).model_dump(mode='json'))


@pytest.mark.asyncio
async def test_server_create_validation(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession):
    """
    test create server api
    * 400 : 필드 조건 오류
        - server name, description 255자 이하
        - volume size 자연수
        - volume name 255자 이하
    """
    # given long name, description, volume's name, negative volume size
    long_name, long_description, long_volume_name, negative_volume_size \
        = generate_string(256), generate_string(256), generate_string(256), -1
    request = {
        "name": long_name,
        "description": long_description,
        "flavor_id": "1",
        "volume": {
            "name": long_volume_name,
            "size": negative_volume_size,
            "image_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        }
    }

    # when
    response = await test_client_no_token.post('/api/servers/', json=request)

    # then
    assert response.status_code == 400

    expected_errors = [
        ErrorContent(detail={'input': long_name, 'loc': ['body', 'name']}, error_type='string_too_long',
                     message='String should have at most 255 characters'),
        ErrorContent(detail={'input': long_description, 'loc': ['body', 'description']}, error_type='string_too_long',
                     message='String should have at most 255 characters'),
        ErrorContent(detail={'input': long_volume_name, 'loc': ['body', 'volume', 'name']},
                     error_type='string_too_long', message='String should have at most 255 characters'),
        ErrorContent(detail={'input': negative_volume_size, 'loc': ['body', 'volume', 'size']},
                     error_type='greater_than_equal', message='Input should be greater than or equal to 1')
    ]
    assert response.json() == [err.__dict__ for err in expected_errors]


async def test_server_create_name_duplicated(test_client_no_token: httpx.AsyncClient, basic_server: Server):
    """
    test create server api
    * 409 : 이미 해당 이름의 서버 존재하는 경우
    """
    # given
    request = {
        "name": basic_server.name,
        "description": "description",
        "flavor_id": "1",
        "volume": {
            "name": "volume_name",
            "size": 1,
            "image_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        }
    }
    # when
    response = await test_client_no_token.post('/api/servers/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_SERVER_NAME_DUPLICATED, detail='').__dict__


async def test_server_create_volume_name_duplicated(test_client_no_token: httpx.AsyncClient,
                                                    basic_server_with_root_volume: (Server, Volume)):
    """
    test create server api
    * 409 : 이미 해당 이름의 볼륨 존재하는 경우
    """
    # given
    _, cur_volume = basic_server_with_root_volume
    request = {
        "name": generate_string(10),
        "description": "description",
        "flavor_id": "1",
        "volume": {
            "name": cur_volume.name,
            "size": 1,
            "image_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        }
    }
    # when
    response = await test_client_no_token.post('/api/servers/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_NAME_DUPLICATED, detail='').__dict__


@pytest.mark.asyncio
async def test_server_create_flavor_not_found(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession,
                                              mocker: MockFixture):
    """
    test create server api
    * 404 : 해당 flavor가 없는 경우
    """
    # given
    flavor_id = generate_string(10)
    mocker.patch('backend.service.server.nova_client.show_flavor_details',
                 nova_client_mock.show_flavor_details_not_found)
    request = {
        "name": "server_with_invalid_flavor_id",
        "description": "invalid flavor id",
        "flavor_id": flavor_id,
        "volume": {
            "name": "volume_name",
            "size": 1,
            "image_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        }
    }
    # when
    response = await test_client_no_token.post('/api/servers/', json=request)

    # then
    assert response.status_code == 404
    assert response.json() == ErrorContent(error_type='error', message=ERR_FLAVOR_NOT_FOUND,
                                           detail=f'flavor (id: {flavor_id}) not found').__dict__


@pytest.mark.asyncio
async def test_server_create_image_not_found(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession,
                                             mocker: MockFixture):
    """
    test create server api
    * 404 : 해당 image가 없는 경우
    """
    # given
    image_id = uuid.uuid4()
    request = {
        "name": "server_with_invalid_image_id",
        "description": "invalid image id",
        "flavor_id": "1",
        "volume": {
            "name": "volume_name",
            "size": 1,
            "image_id": f"{image_id}"
        }
    }
    mocker.patch('backend.service.server.nova_client.show_flavor_details',
                 nova_client_mock.show_flavor_details_success)
    mocker.patch('backend.service.server.glance_client.show_image',
                 glance_client_mock.show_image_not_found)

    # when
    response = await test_client_no_token.post('/api/servers/', json=request)

    # then
    assert response.status_code == 404
    assert response.json() == ErrorContent(error_type='error', message=ERR_IMAGE_NOT_FOUND,
                                           detail=f'image (id: {image_id}) not found').__dict__


async def test_server_quota_server_limit(test_client_no_token: httpx.AsyncClient, mocker: MockFixture):
    """
    test create server api
    * 409 : server limit over
    """
    # given
    request = {
        "name": "server_with_limit",
        "description": "server limit",
        "flavor_id": '1',
        "volume": {
            "name": "volume_name",
            "size": 16,
            "image_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        }
    }

    # given [MOCK] NOVA flavor 검증 통과 (4core, 8GB ram, 16GB disk)
    flavorDto = nova_client_mock.show_flavor_details_basic()
    mocker.patch('backend.service.server.nova_client.show_flavor_details', return_value=flavorDto)
    # given [MOCK] GLANCE image 검증 통과
    mocker.patch('backend.service.server.glance_client.show_image', glance_client_mock.show_image_success)
    # given [MOCK] NOVA quota : 0개 여유, cpu 4개, ram 8GB (부족)
    mocker.patch('backend.service.server.nova_client.show_rate_and_absolute_limits',
                 return_value=ServerRemainLimitDto(remain_instances=0, remain_cores=flavorDto.vcpus,
                                                   remain_rams=flavorDto.ram))
    # when
    response = await test_client_no_token.post('/api/servers/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_SERVER_LIMIT_OVER, detail='').__dict__


async def test_server_quota_volume_limit(test_client_no_token: httpx.AsyncClient, mocker: MockFixture):
    """
    test create server api
    * 409 : volume limit over
    """
    # given
    request = {
        "name": "server_with_volume_limit",
        "description": "volume limit",
        "flavor_id": '1',
        "volume": {
            "name": "volume_name",
            "size": 16,
            "image_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        }
    }
    # given [MOCK] NOVA flavor 검증 통과 (4core, 8GB ram, 16GB disk)
    flavorDto = nova_client_mock.show_flavor_details_basic()
    mocker.patch('backend.service.server.nova_client.show_flavor_details', return_value=flavorDto)
    # given [MOCK] GLANCE image 검증 통과
    mocker.patch('backend.service.server.glance_client.show_image', glance_client_mock.show_image_success)
    # given [MOCK] NOVA quota : 1개 여유, cpu 4개, ram 8GB 여유 (딱 맞게)
    mocker.patch('backend.service.server.nova_client.show_rate_and_absolute_limits',
                 return_value=ServerRemainLimitDto(remain_instances=1, remain_cores=flavorDto.vcpus,
                                                   remain_rams=flavorDto.ram))
    # given [MOCK] CINDER quota 체크 : 1개 여유, disk 15GB 여유 (부족)
    mocker.patch('backend.service.server.cinder_client.show_absolute_limits_for_project',
                 return_value=VolumeRemainLimitDto(remain_cnt=1, remain_size=flavorDto.disk - 1))

    # when
    response = await test_client_no_token.post('/api/servers/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_LIMIT_OVER, detail='').__dict__


@pytest.mark.asyncio
async def test_server_create_size_conflict(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession,
                                           mocker: MockFixture):
    """
    test create server api
    * 409 : image size보다 요청 volume size가 작은 경우
    """
    # given
    image_id = uuid.uuid4()
    request = {
        "name": "server_small_volume",
        "description": "small volume",
        "flavor_id": "1",
        "volume": {
            "name": "small_volume_name",
            "size": 1,
            "image_id": f"{image_id}"
        }
    }
    mocker.patch('backend.service.server.nova_client.show_flavor_details',
                 nova_client_mock.show_flavor_details_success)
    mocker.patch('backend.service.server.glance_client.show_image', glance_client_mock.show_image_larger_than_1)

    # when
    response = await test_client_no_token.post('/api/servers/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_IMAGE_SIZE_CONFLICT, detail='').__dict__


@pytest.mark.asyncio
async def test_server_update_basic(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession,
                                   basic_server: Server, mocker: MockFixture):
    """
    test server update api
    * 200 : 성공
    """
    # given
    cur_server = basic_server
    name, description = 'updated_name', 'updated_description'
    request = {'name': name, 'description': description}
    # given [MOCK] update info success
    mocker.patch('backend.service.server.nova_client.update_server',
                 return_value=ServerUpdateDto(name=name, description=description))
    # given [MOCK] response mapper
    mocker.patch.object(ServerResponse, 'mapper', ServerResponseMock.mapper)
    # given expected server after update
    cur_server.name, cur_server.description = name, description

    # when
    response = await test_client_no_token.patch(f'api/servers/{cur_server.server_id}/', json=request)

    # then
    assert response.status_code == 200
    assert response.json() == (await ServerResponseMock.mapper(cur_server)).model_dump(mode='json')


@pytest.mark.asyncio
async def test_server_update_validation(test_client_no_token: httpx.AsyncClient, basic_server: Server):
    """
    test server update api
    * 400 : 입력 필드 조건 오류(필드 255자 넘는 경우)
    """
    # given
    cur_server = basic_server
    long_name, long_description = generate_string(256), generate_string(256)
    long_request = {'name': long_name, 'description': long_description}
    # given expected response
    expected_errors = [
        ErrorContent(detail={'input': long_name, 'loc': ['body', 'name']}, error_type='string_too_long',
                     message='String should have at most 255 characters'),
        ErrorContent(detail={'input': long_description, 'loc': ['body', 'description']}, error_type='string_too_long',
                     message='String should have at most 255 characters')]

    # when
    response = await test_client_no_token.patch(f'api/servers/{cur_server.server_id}/', json=long_request)

    # then
    assert response.status_code == 400
    assert response.json() == [err.__dict__ for err in expected_errors]


@pytest.mark.asyncio
async def test_server_update_name_duplicated(test_client_no_token: httpx.AsyncClient, basic_server: Server,
                                             basic_server_with_port: Server):
    """
    test server update api
    * 409 : 이미 존재하는 이름
    """
    # given
    cur_server = basic_server
    name_will_be = basic_server_with_port.name
    request = {'name': name_will_be, 'description': generate_string(10)}

    # when
    response = await test_client_no_token.patch(f'api/servers/{cur_server.server_id}/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_SERVER_NAME_DUPLICATED, detail='').__dict__


@pytest.mark.asyncio
async def test_server_update_already_deleted(test_client_no_token: httpx.AsyncClient, deleted_server: Server):
    """
    test server update api
    * 409 : 서버 삭제된 경우
    """
    # given
    cur_server = deleted_server
    request = {'name': generate_string(10), 'description': generate_string(10)}

    # when
    response = await test_client_no_token.patch(f'api/servers/{cur_server.server_id}/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_SERVER_ALREADY_DELETED, detail='').__dict__


@pytest.mark.asyncio
async def test_server_delete_success(test_client_no_token: httpx.AsyncClient, all_connected_server: Server,
                                     mocker: MockFixture, test_db_session: AsyncSession):
    """
    test server delete api
    * 204 : 서버 삭제 성공
    """
    # given
    cur_server = all_connected_server

    # given [MOCK] delete_server success
    mocker.patch('backend.service.server.nova_client.delete_server', return_value=None)

    # when
    response = await test_client_no_token.delete(f'api/servers/{cur_server.server_id}/')

    # then
    assert response.status_code == 204

    # then check db
    await test_db_session.commit()
    await test_db_session.refresh(cur_server, attribute_names=['deleted_at', 'volumes', 'floatingip', 'fk_port_id'])

    assert cur_server.fk_port_id is None
    assert cur_server.deleted
    assert (await cur_server.awaitable_attrs.volumes) == []
    assert (await cur_server.awaitable_attrs.floatingip) is None


@pytest.mark.asyncio
async def test_server_delete_conflict(test_client_no_token: httpx.AsyncClient, deleted_server: Server):
    """
    test server delete api
    * 409 : 이미 삭제된 서버인 경우
    """
    # given
    cur_server = deleted_server

    # when
    response = await test_client_no_token.delete(f'api/servers/{cur_server.server_id}/')

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_SERVER_ALREADY_DELETED, detail='').__dict__


@pytest.mark.asyncio
async def test_update_server_power_success(test_client_no_token: httpx.AsyncClient, basic_server: Server,
                                           mocker: MockFixture):
    """
    test server power update api
    * 202 : 상태 변경 완료
    """
    # given
    cur_server = basic_server
    request = {
        'power_state': 'hard-reboot'
    }
    # given [MOCK] nova run an action
    mocker.patch('backend.service.server.nova_client.run_an_action', return_value=None)
    # given [MOCK] response
    mocker.patch.object(ServerResponse, 'mapper', ServerResponseMock.mapper)
    # when
    response = await test_client_no_token.patch(f'api/servers/{cur_server.server_id}/power/', json=request)

    # then
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_server_attach_volume_success(test_client_no_token: httpx.AsyncClient,
                                            basic_server_with_root_volume: (Server, Volume), basic_volume: Volume,
                                            mocker: MockFixture):
    """
    test server attach volume api
    * 202 : 볼륨 attach 성공
    """
    # given
    cur_server, root_volume = basic_server_with_root_volume
    cur_volume = basic_volume
    request = {
        'volume_id': f"{cur_volume.volume_id}"
    }
    # given [MOCK] NOVA : 서버 상태 active
    mocker.patch('backend.service.server.nova_client.show_server_details',
                 return_value=nova_client_mock.show_server_details_with_status(server=cur_server,
                                                                               status=ServerStatus.ACTIVE))
    # given [MOCK] CINDER : 볼륨 상태 available
    mocker.patch('backend.service.server.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(basic_volume, VolumeStatus.AVAILABLE))
    # given [MOCK] NOVA : attach 요청 성공
    mocker.patch('backend.service.server.nova_client.attach_volume_to_instance', return_value=None)
    # given [MOCK] task 즉시 종료
    mocker.patch('backend.service.server.ServerService._task_after_attach_volume', return_value=None)
    # when
    response = await test_client_no_token.post(f'api/servers/{cur_server.server_id}/volumes/', json=request)

    # then
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_server_attach_volume_not_found(test_client_no_token: httpx.AsyncClient,
                                              basic_server_with_root_volume: (Server, Volume),
                                              ):
    """
    test server attach volume api
    * 404 : 존재하지 않는 볼륨인 경우
    """
    # given
    cur_server, _ = basic_server_with_root_volume
    invalid_request = {
        "volume_id": f"{uuid.uuid4()}"
    }

    # when wrong volume_id
    response = await test_client_no_token.post(f'api/servers/{cur_server.server_id}/volumes/',
                                               json=invalid_request)
    # then
    assert response.status_code == 404

    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_NOT_FOUND,
                                           detail='').__dict__


@pytest.mark.asyncio
async def test_server_attach_server_not_found(test_client_no_token: httpx.AsyncClient, basic_volume: Volume):
    """
    test server attach volume api
    * 404 : 존재하지 않는 서버인 경우
    """
    # given
    cur_volume = basic_volume
    valid_request = {
        "volume_id": f"{cur_volume.volume_id}"
    }
    wrong_server_id = uuid.uuid4()
    # when wrong server id
    response = await test_client_no_token.post(f'api/servers/{wrong_server_id}/volumes/',
                                               json=valid_request)

    # then
    assert response.status_code == 404

    assert response.json() == ErrorContent(error_type='error', message=ERR_SERVER_NOT_FOUND,
                                           detail='').__dict__


@pytest.mark.asyncio
async def test_server_attach_server_deleted(test_client_no_token: httpx.AsyncClient, deleted_server: Server,
                                            basic_volume: Volume):
    """
    test server attach volume api
    * 409 : 서버 삭제된 경우
    """
    # given
    cur_server = deleted_server
    cur_volume = basic_volume
    request = {'volume_id': f'{cur_volume.volume_id}'}

    # when
    response = await test_client_no_token.post(f'api/servers/{cur_server.server_id}/volumes/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_SERVER_ALREADY_DELETED, detail='').__dict__


@pytest.mark.asyncio
async def test_server_attach_volume_deleted(test_client_no_token: httpx.AsyncClient, deleted_volume: Volume,
                                            basic_server: Server):
    """
    test server attach volume api
    * 409 : 볼륨 삭제된 경우
    """
    # given
    cur_server = basic_server
    cur_volume = deleted_volume
    request = {'volume_id': f'{cur_volume.volume_id}'}
    # when
    response = await test_client_no_token.post(f'api/servers/{cur_server.server_id}/volumes/', json=request)
    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_ALREADY_DELETED, detail='').__dict__


@pytest.mark.asyncio
async def test_server_detach_volume_success(test_client_no_token: httpx.AsyncClient, all_connected_server: Server,
                                            mocker: MockFixture):
    """
    test server attach volume api
    * 202 : 볼륨 해제 성공
    """
    # given
    cur_server = all_connected_server
    volumes = await cur_server.awaitable_attrs.volumes
    request = {}
    for volume in volumes:
        if not volume.is_root_volume:
            cur_volume = volume
    request = {'volume_id': f'{cur_volume.volume_id}'}

    # given [MOCK] NOVA : 서버 상태 active
    mocker.patch('backend.service.server.nova_client.show_server_details',
                 return_value=nova_client_mock.show_server_details_with_status(server=cur_server,
                                                                               status=ServerStatus.ACTIVE))
    # given [MOCK] CINDER : 볼륨 상태 in_use
    mocker.patch('backend.service.server.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(cur_volume, VolumeStatus.IN_USE))
    # given [MOCK] NOVA : detach 요청 성공
    mocker.patch('backend.service.server.nova_client.detach_volume_to_instance', return_value=None)
    # given [MOCK] task 즉시 종료
    mocker.patch('backend.service.server.ServerService._task_after_detach_volume', return_value=None)

    # when
    response = await test_client_no_token.request(method='DELETE', url=f'api/servers/{cur_server.server_id}/volumes/',
                                                  json=request)

    # then
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_server_detach_not_connected(test_client_no_token: httpx.AsyncClient, basic_volume: Volume,
                                           basic_server: Server):
    """
    test server attach volume api
    * 409 : 볼륨, 서버가 서로 연결되지 않은 경우
    """
    # given
    cur_server, cur_volume = basic_server, basic_volume
    request = {'volume_id': f'{cur_volume.volume_id}'}

    # when
    response = await test_client_no_token.request('DELETE', url=f'api/servers/{cur_server.server_id}/volumes/',
                                                  json=request)
    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_SERVER_VOLUME_NOT_CONNECTED,
                                           detail='').__dict__


@pytest.mark.asyncio
async def test_server_detach_root_volume(test_client_no_token: httpx.AsyncClient, all_connected_server: Server):
    """
    test server attach volume api
    * 409 : 루트 볼륨 해제하려는 경우
    """
    # given
    cur_server = all_connected_server
    volumes = await cur_server.awaitable_attrs.volumes
    request = {}
    for volume in volumes:
        if volume.is_root_volume:
            request = {'volume_id': f'{volume.volume_id}'}

    # when
    response = await test_client_no_token.request('DELETE', url=f'api/servers/{cur_server.server_id}/volumes/',
                                                  json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_SERVER_ROOT_VOLUME_CANT_DETACH,
                                           detail='').__dict__
