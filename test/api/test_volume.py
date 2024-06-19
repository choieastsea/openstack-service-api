import random
import uuid
import httpx
import pytest
from pytest_mock import MockFixture
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exception_handler import ErrorContent
from backend.model.server import Server
from backend.model.volume import Volume, VolumeStatus
from backend.schema.response import VolumeResponse
from backend.schema.volume import VolumeRemainLimitDto
from backend.util.constant import (ERR_VOLUME_NOT_FOUND, ERR_VOLUME_NAME_DUPLICATED, ERR_VOLUME_LIMIT_OVER,
                                   ERR_VOLUME_ALREADY_DELETED, ERR_VOLUME_SERVER_CONFLICT, ERR_VOLUME_STATUS_CONFLICT,
                                   ERR_VOLUME_SIZE_UPGRADE_CONFLICT)
from test.conftest import generate_string
from test.mock.cinder import cinder_client_mock
from test.mock.response import VolumeResponseMock
from test.mock.task import task_after_extend_volume_end_immediately


@pytest.mark.asyncio
async def test_volume_list_basic(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession,
                                 mocker: MockFixture):
    """
    test volume list api
    * 200 : 성공
    """
    # given
    volumes = await test_db_session.scalars(select(Volume).offset(0).limit(10))
    expected_response = await VolumeResponseMock.mapper(list(volumes))
    mocker.patch.object(VolumeResponse, 'mapper', VolumeResponseMock.mapper)

    # when
    response = await test_client_no_token.get('/api/volumes/')

    # then
    assert response.status_code == 200
    assert response.json() == [el.model_dump(mode='json') for el in expected_response]


@pytest.mark.asyncio
async def test_volume_get_basic(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession,
                                basic_volume: Volume, mocker: MockFixture):
    """
    test volume get api
    * 200 : 성공
    """
    # given
    cur_volume = basic_volume
    actual_volume = await test_db_session.scalar(select(Volume).filter(Volume.volume_id == cur_volume.volume_id))
    mocker.patch.object(VolumeResponse, 'mapper', VolumeResponseMock.mapper)

    # when
    response = await test_client_no_token.get(f'/api/volumes/{cur_volume.volume_id}/')

    # then
    assert response.status_code == 200
    assert response.json() == (await VolumeResponseMock.mapper(actual_volume)).model_dump(mode='json')


@pytest.mark.asyncio
async def test_volume_get_not_found(test_client_no_token: httpx.AsyncClient):
    """
    test volume get api
    * 404 : not found
    """
    # given
    id = uuid.uuid4()
    response = await test_client_no_token.get(f'/api/volumes/{id}/')
    # then
    assert response.status_code == 404
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_NOT_FOUND,
                                           detail=f'volume (id : {id}) not found').__dict__


@pytest.mark.asyncio
async def test_volume_create_success(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                     test_db_session: AsyncSession):
    """
    test create volume api
    * 202 : 성공 및 볼륨 생성 완료 확인
    """
    # given
    request = {
        "size": 1,
        "name": "volume_create_success",
        "description": "volume create sucess"
    }
    volume_created_id = uuid.uuid4()
    # given [MOCK] cinder 여유 공간 확인 (2개 가능, 2GB 가능)
    mocker.patch('backend.service.volume.cinder_client.show_absolute_limits_for_project',
                 return_value=VolumeRemainLimitDto(remain_cnt=2, remain_size=2))
    # given [MOCK] cinder 볼륨 생성 성공
    mocker.patch('backend.service.volume.cinder_client.create_volume',
                 return_value=cinder_client_mock.create_volume_success(volume_created_id, request))
    # given [MOCK] volume status : CREATING
    mocker.patch('backend.schema.response.get_volume_status_by_id_or_deleted', return_value=VolumeStatus.CREATING)

    # when
    response = await test_client_no_token.post('/api/volumes/', json=request)

    # then
    assert response.status_code == 202

    # then check db
    actual_volume = await test_db_session.scalar(select(Volume).filter(Volume.volume_id == volume_created_id))
    expected_response = (await VolumeResponseMock.mapper(actual_volume, status=VolumeStatus.CREATING)).model_dump(
        mode='json')
    assert response.json() == expected_response


@pytest.mark.asyncio
async def test_volume_create_validation(test_client_no_token: httpx.AsyncClient):
    """
    test create volume api
    * 400 : 필드 조건 오류
        - volume name, description 255자 이하
        - size 1이상의 정수
    """
    # given
    long_name, long_description, negative_volume_size = generate_string(256), generate_string(256), -1

    request = {
        "name": long_name,
        "description": long_description,
        "size": negative_volume_size
    }

    # when
    response = await test_client_no_token.post('/api/volumes/', json=request)

    # then
    assert response.status_code == 400

    expected_errors = [
        ErrorContent(detail={'input': negative_volume_size, 'loc': ['body', 'size']},
                     error_type='greater_than_equal', message='Input should be greater than or equal to 1'),
        ErrorContent(detail={'input': long_name, 'loc': ['body', 'name']}, error_type='string_too_long',
                     message='String should have at most 255 characters'),
        ErrorContent(detail={'input': long_description, 'loc': ['body', 'description']}, error_type='string_too_long',
                     message='String should have at most 255 characters')
    ]

    assert response.json() == [err.__dict__ for err in expected_errors]


async def test_volume_create_name_duplicated(test_client_no_token: httpx.AsyncClient, basic_volume: Volume):
    """
    test create volume api
    * 409 : 이미 해당 이름의 볼륨 존재하는 경우
    """
    # given
    request = {
        "name": basic_volume.name,
        "description": "description",
        "size": 1
    }

    # when
    response = await test_client_no_token.post('/api/volumes/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_NAME_DUPLICATED, detail='').__dict__


async def test_volume_create_size_fail(test_client_no_token: httpx.AsyncClient, mocker: MockFixture):
    """
    test create volume api
    * 409 : openstack에 여유 볼륨 공간(GB)이 없는 경우
    """
    # given
    request = {
        "size": 10,
        "name": "volume_with_10gb",
        "description": "volume with 10gb"
    }
    # given [MOCK] cinder 여유 공간 확인 (2개 가능, 2GB 가능)
    mocker.patch('backend.service.volume.cinder_client.show_absolute_limits_for_project',
                 return_value=VolumeRemainLimitDto(remain_cnt=2, remain_size=2))

    # when
    response = await test_client_no_token.post('/api/volumes/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_LIMIT_OVER, detail='').__dict__


async def test_volume_create_cnt_fail(test_client_no_token: httpx.AsyncClient, mocker: MockFixture):
    """
    test create volume api
    * 409 : openstack에 여유 볼륨 인스턴스(갯수)가 없는 경우
    """
    # given
    request = {
        "size": 10,
        "name": "volume_with_10gb",
        "description": "volume with 10gb"
    }
    # given [MOCK] cinder 여유 공간 확인 (0개 가능, 100GB 가능)
    mocker.patch('backend.service.volume.cinder_client.show_absolute_limits_for_project',
                 return_value=VolumeRemainLimitDto(remain_cnt=0, remain_size=100))

    # when
    response = await test_client_no_token.post('/api/volumes/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_LIMIT_OVER, detail='').__dict__


async def test_update_volume_info_success(test_client_no_token: httpx.AsyncClient, test_db_session: AsyncSession,
                                          basic_volume: Volume, mocker: MockFixture):
    """
    test update volume info api
    * 200 : 업데이트 성공
    """
    # given
    cur_volume = basic_volume
    request = {
        'name': 'updated_name',
        'description': 'updated_description'
    }
    # given [MOCK] cinder 볼륨 업데이트 성공
    mocker.patch('backend.service.volume.cinder_client.update_a_volume',
                 return_value=cinder_client_mock.update_volume_success(cur_volume, request))
    # given [MOCK] response mapper
    mocker.patch.object(VolumeResponse, 'mapper', VolumeResponseMock.mapper)

    # when
    response = await test_client_no_token.patch(f'/api/volumes/{cur_volume.volume_id}/', json=request)

    # then
    assert response.status_code == 200
    assert response.json() == (await VolumeResponseMock.mapper(cur_volume)).model_dump(mode='json')


@pytest.mark.asyncio
async def test_update_volume_validation(test_client_no_token: httpx.AsyncClient, basic_volume: Volume):
    """
    test update volume info api
    * 400 : 입력 필드 오류 (255자 이상)
    """
    # given
    cur_volume = basic_volume
    long_name, long_description = generate_string(256), generate_string(256)

    request = {
        "name": long_name,
        "description": long_description
    }

    # when
    response = await test_client_no_token.patch(f'/api/volumes/{cur_volume.volume_id}/', json=request)

    # then
    assert response.status_code == 400

    expected_errors = [
        ErrorContent(detail={'input': long_name, 'loc': ['body', 'name']}, error_type='string_too_long',
                     message='String should have at most 255 characters'),
        ErrorContent(detail={'input': long_description, 'loc': ['body', 'description']}, error_type='string_too_long',
                     message='String should have at most 255 characters')
    ]

    assert response.json() == [err.__dict__ for err in expected_errors]


@pytest.mark.asyncio
async def test_update_volume_already_deleted(test_client_no_token: httpx.AsyncClient, deleted_volume: Volume):
    """
    test update volume info api
    * 409 : 이미 삭제된 볼륨인 경우
    """
    # given
    cur_volume = deleted_volume
    request = {
        'name': 'updated_name',
        'description': 'updated_description'
    }
    # when
    response = await test_client_no_token.patch(f'/api/volumes/{cur_volume.volume_id}/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_ALREADY_DELETED, detail='').__dict__


@pytest.mark.asyncio
async def test_update_volume_name_duplicated(test_client_no_token: httpx.AsyncClient, basic_volume: Volume,
                                             basic_server_with_root_volume: (Server, Volume)):
    """
    test update volume info api
    * 409 : 이미 존재하는 이름의 볼륨인 경우
    """
    # given
    _, cur_volume = basic_server_with_root_volume
    another_volume = basic_volume
    request = {
        'name': another_volume.name,
        'description': 'duplicated name'
    }
    response = await test_client_no_token.patch(f'/api/volumes/{cur_volume.volume_id}/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_NAME_DUPLICATED, detail='').__dict__


@pytest.mark.asyncio
async def test_delete_volume_success(test_client_no_token: httpx.AsyncClient, basic_volume: Volume,
                                     mocker: MockFixture, test_db_session: AsyncSession):
    """
    test volume delete api
    * 204 : 볼륨 삭제 성공
    """
    # given
    cur_volume = basic_volume
    # given [MOCK] cinder 볼륨 상태 AVAILABLE
    mocker.patch('backend.service.volume.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(volume=cur_volume,
                                                                                status=VolumeStatus.AVAILABLE))
    # given [MOCK] cinder 볼륨 삭제 성공
    mocker.patch('backend.service.volume.cinder_client.delete_a_volume',
                 return_value=None)

    # when
    response = await test_client_no_token.delete(f'/api/volumes/{cur_volume.volume_id}/')

    # then
    assert response.status_code == 204
    # then check volume is soft-deleted
    await test_db_session.refresh(cur_volume)
    assert cur_volume.deleted is True


@pytest.mark.asyncio
async def test_delete_volume_attached(test_client_no_token: httpx.AsyncClient,
                                      basic_server_with_root_volume: (Server, Volume)):
    """
    test volume delete api
    * 409 : 서버와 연결되어 있는 경우
    """
    # given
    server, cur_volume = basic_server_with_root_volume

    # when
    response = await test_client_no_token.delete(f'/api/volumes/{cur_volume.volume_id}/')

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_SERVER_CONFLICT,
                                           detail=f'server id: {server.server_id}').__dict__


@pytest.mark.asyncio
async def test_delete_volume_status_bad(test_client_no_token: httpx.AsyncClient,
                                        basic_volume: Volume, mocker: MockFixture):
    """
    test volume delete api
    * 409 : 삭제 불가능한 상태인 경우
    """
    # given
    cur_volume = basic_volume
    # given status : 볼륨 삭제가능하지 않은 상태인 경우
    random_bad_status = random.choice([status for status in list(VolumeStatus) if status not in (
        VolumeStatus.AVAILABLE, VolumeStatus.IN_USE, VolumeStatus.ERROR, VolumeStatus.ERROR_RESTORING,
        VolumeStatus.ERROR_EXTENDING)])
    # given [MOCK] cinder 볼륨 상태 : available, in-use, error, error_restoring, error_extending가 아닌 경우
    mocker.patch('backend.service.volume.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(cur_volume, random_bad_status))

    # when
    response = await test_client_no_token.delete(f'/api/volumes/{cur_volume.volume_id}/')
    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_STATUS_CONFLICT, detail='').__dict__


@pytest.mark.asyncio
async def test_extend_volume_size_success(test_client_no_token: httpx.AsyncClient, basic_volume: Volume,
                                          mocker: MockFixture):
    """
    test volume extend size api
    * 202 : 볼륨 사이즈 확장 성공
    """
    # given
    cur_volume = basic_volume
    request = {'new_size': cur_volume.size + 1}
    # given [MOCK] cinder 정보 get 성공 (status: available)
    mocker.patch('backend.service.volume.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(volume=cur_volume,
                                                                                status=VolumeStatus.AVAILABLE))
    # given [MOCK] quota 남은 용량 확인 성공 (instance 1개, 1GB의 여유 공간)
    mocker.patch('backend.service.volume.cinder_client.show_absolute_limits_for_project',
                 return_value=VolumeRemainLimitDto(remain_cnt=1, remain_size=1))
    # given [MOCK] cinder 용량 증가 요청 성공
    mocker.patch('backend.service.volume.cinder_client.extend_a_volume_size', return_value=None)
    # given [MOCK] task 즉시 종료
    mocker.patch('backend.service.volume.VolumeService._task_after_extend_volume',
                 task_after_extend_volume_end_immediately)

    # when
    response = await test_client_no_token.patch(f'/api/volumes/{cur_volume.volume_id}/size/', json=request)

    # then
    assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_extend_volume_size_validation(test_client_no_token: httpx.AsyncClient, basic_volume: Volume):
        """
        test volume extend size api
        * 400 : 입력 오류 (2 이하로 증가 요청시 오류)
        """
        # given
        cur_volume = basic_volume
        request = {'new_size': -1}

        # when
        response = await test_client_no_token.patch(f'/api/volumes/{cur_volume.volume_id}/size/', json=request)

        # then
        assert response.status_code == 400
        assert response.json() == ErrorContent(error_type='greater_than_equal',
                                               message='Input should be greater than or equal to 2',
                                               detail={'input': request['new_size'],
                                                       'loc': ['body', 'new_size']}).__dict__


@pytest.mark.asyncio
async def test_extend_volume_size_not_available(test_client_no_token: httpx.AsyncClient, basic_volume: Volume,
                                                mocker: MockFixture):
    """
    test volume extend size api
    * 409 : volume status가 available이 아닌 경우
    """
    # given
    cur_volume = basic_volume
    request = {'new_size': cur_volume.size + 1}
    # given [MOCK] cinder 정보 get 성공 (status: error)
    mocker.patch('backend.service.volume.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(volume=cur_volume,
                                                                                status=VolumeStatus.ERROR))

    # when
    response = await test_client_no_token.patch(f'/api/volumes/{cur_volume.volume_id}/size/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_STATUS_CONFLICT, detail='').__dict__


@pytest.mark.asyncio
async def test_extend_volume_size_smaller(test_client_no_token: httpx.AsyncClient, basic_volume: Volume,
                                          mocker: MockFixture):
    """
    test volume extend size api
    * 409 : volume size가 기존보다 더 작아지는 경우
    """
    # given
    cur_volume = basic_volume
    request = {'new_size': cur_volume.size - 1}
    # given [MOCK] cinder 정보 get 성공 (status : available)
    mocker.patch('backend.service.volume.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(volume=cur_volume,
                                                                                status=VolumeStatus.AVAILABLE))
    # when
    response = await test_client_no_token.patch(f'/api/volumes/{cur_volume.volume_id}/size/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_SIZE_UPGRADE_CONFLICT,
                                           detail=f'current volume size : {cur_volume.size}GB').__dict__


@pytest.mark.asyncio
async def test_extend_volume_size_quota_over(test_client_no_token: httpx.AsyncClient, basic_volume: Volume,
                                             mocker: MockFixture):
    """
    test volume extend size api
    * 409 : 추가 용량보다 남은 quota가 부족한 경우
    """
    # given
    cur_volume = basic_volume
    request = {'new_size': cur_volume.size + 10}
    # given [MOCK] cinder 정보 get 성공 (status: available)
    mocker.patch('backend.service.volume.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(volume=cur_volume,
                                                                                status=VolumeStatus.AVAILABLE))
    # given [MOCK] quota 남은 용량 확인 성공 (instance 1개, 1GB의 여유 공간)
    mocker.patch('backend.service.volume.cinder_client.show_absolute_limits_for_project',
                 return_value=VolumeRemainLimitDto(remain_cnt=1, remain_size=1))

    # when
    response = await test_client_no_token.patch(f'/api/volumes/{cur_volume.volume_id}/size/', json=request)

    # then
    assert response.status_code == 409
    assert response.json() == ErrorContent(error_type='error', message=ERR_VOLUME_LIMIT_OVER, detail='').__dict__
