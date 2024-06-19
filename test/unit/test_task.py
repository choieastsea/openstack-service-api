import datetime
import uuid
import httpx
import pytest
from pytest_mock import MockFixture
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.client import nova_client as nova_client_from_server, cinder_client as cinder_client_from_server
from backend.model.server import Server
from backend.model.volume import VolumeStatus, Volume
from backend.repository.server import ServerRepository
from backend.repository.volume import VolumeRepository
from backend.schema.server import ServerNetInterfaceDto
from backend.schema.volume import VolumeDto
from backend.service.server import ServerService
from backend.service.volume import VolumeService
from test.api.test_server import SETTINGS
from test.mock.cinder import cinder_client_mock
from test.mock.nova import nova_client_mock


@pytest.mark.asyncio
async def test_task_server_volume_created(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                          test_db_session: AsyncSession, basic_server: Server):
    """
    test task_after_server_create
    * 1. 서버 생성 이후(basic_server) 태스크 성공
    """
    # given input
    cur_server = basic_server
    port_id, fixed_address = uuid.uuid4(), '214.214.214.214'
    new_volume_id, new_volume_name = uuid.uuid4(), 'new_volume_name'
    # given service
    server_service = ServerService(serverRepository=ServerRepository(session=test_db_session),
                                   volumeRepository=VolumeRepository(session=test_db_session))
    # given [MOCK] show server & volume details : 서버 생성 & 볼륨 연결 완료
    curServerDto, volume_id_list = nova_client_mock.show_server_details_success_with_active_server(cur_server,
                                                                                                   new_volume_id)
    mocker.patch.object(nova_client_from_server, 'show_server_details_with_volume_ids',
                        return_value=(curServerDto, volume_id_list))
    # given [MOCK] show port interface : 네트워크 연결 완료
    mocker.patch.object(nova_client_from_server, 'show_port_interface_details',
                        return_value=ServerNetInterfaceDto(port_id=port_id, fixed_address=fixed_address))
    # given [MOCK] show volume detail : 빈 이름의 루트 볼륨 찾기 완료
    volume_created = VolumeDto(volume_id=new_volume_id, name='', volume_type='HDD', size=1,
                               fk_server_id=cur_server.server_id,
                               fk_project_id=SETTINGS.OPENSTACK_PROJECT_ID, fk_image_id=uuid.uuid4(),
                               status=VolumeStatus.IN_USE, created_at=datetime.datetime.now().replace(microsecond=0)
                               )
    mocker.patch.object(cinder_client_from_server, 'show_volume_detail', return_value=volume_created)

    # given [MOCK] update volume name
    volume_updated = VolumeDto(**volume_created.model_dump(exclude={'name'}), name=new_volume_name)  # 새로운 볼륨 이름으로 대체
    mocker.patch.object(cinder_client_from_server, 'update_a_volume', return_value=volume_updated)

    # when
    await server_service._task_after_create_server(cur_server, volume_name=new_volume_name, token='', interval_time=0,
                                                   polling_limit=1)
    # then check volume
    actual_volume = await test_db_session.scalar(select(Volume).filter(Volume.volume_id == new_volume_id))
    assert isinstance(actual_volume, Volume)
    actual_volume_dict = actual_volume.__dict__
    expected_volume_dict = Volume(**volume_updated.model_dump(exclude={'status'})).__dict__
    actual_volume_dict.pop('_sa_instance_state')  # db session instance값 제거한 모든 필드 비교
    expected_volume_dict.pop('_sa_instance_state')
    assert actual_volume_dict == expected_volume_dict


@pytest.mark.asyncio
async def test_task_volume_not_created(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                       test_db_session: AsyncSession, basic_server: Server):
    """
    test task_after_server_create
    * 2. 서버는 생성했지만, 볼륨 생성은 실패한 경우 (basic_server와 연결된 volume 없음)
    """
    # given input
    cur_server = basic_server
    new_volume_id, new_volume_name = uuid.uuid4(), 'wont_create'
    # given service
    server_service = ServerService(serverRepository=ServerRepository(session=test_db_session),
                                   volumeRepository=VolumeRepository(session=test_db_session))
    # given [MOCK] show server & volume details : 서버 생성 완료 & 볼륨 생성 실패
    curServerDto, volume_id_list = nova_client_mock.show_server_details_fail_with_error_server(cur_server)
    mocker.patch.object(nova_client_from_server, 'show_server_details_with_volume_ids',
                        return_value=(curServerDto, volume_id_list))

    # when
    await server_service._task_after_create_server(cur_server, volume_name=new_volume_name, token='', interval_time=0,
                                                   polling_limit=1)

    # then check root volume is not created
    volumes = await basic_server.awaitable_attrs.volumes
    assert len(volumes) == 0


@pytest.mark.asyncio
async def test_task_volume_update_failed(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                         test_db_session: AsyncSession, basic_server: Server):
    """
    test task_after_server_create
    * 3. 볼륨까진 생성했지만, 이름 바꾸지 못한 경우
    """
    # given input
    cur_server = basic_server
    port_id, fixed_address = uuid.uuid4(), '214.214.214.214'
    new_volume_id, new_volume_name = uuid.uuid4(), 'new_volume_name'
    # given service
    server_service = ServerService(serverRepository=ServerRepository(session=test_db_session),
                                   volumeRepository=VolumeRepository(session=test_db_session))
    # given [MOCK] show server & volume details : 서버 생성 & 볼륨 연결 완료
    curServerDto, volume_id_list = nova_client_mock.show_server_details_success_with_active_server(cur_server,
                                                                                                   new_volume_id)
    mocker.patch.object(nova_client_from_server, 'show_server_details_with_volume_ids',
                        return_value=(curServerDto, volume_id_list))
    # given [MOCK] show port interface : 네트워크 연결 완료
    mocker.patch.object(nova_client_from_server, 'show_port_interface_details',
                        return_value=ServerNetInterfaceDto(port_id=port_id, fixed_address=fixed_address))
    # given [MOCK] show volume detail : 빈 이름의 루트 볼륨 찾기 완료
    volume_created = VolumeDto(volume_id=new_volume_id, name='', volume_type='HDD', size=1,
                               fk_server_id=cur_server.server_id,
                               fk_project_id=SETTINGS.OPENSTACK_PROJECT_ID, fk_image_id=uuid.uuid4(),
                               status=VolumeStatus.IN_USE, created_at=datetime.datetime.now().replace(microsecond=0)
                               )
    mocker.patch.object(cinder_client_from_server, 'show_volume_detail', return_value=volume_created)
    mocker.patch.object(cinder_client_from_server, 'update_a_volume',
                        callable=cinder_client_mock.update_a_volume_failed)  # 볼륨 이름 변경시 오류 발생 (500)
    # when
    await server_service._task_after_create_server(cur_server, volume_name=new_volume_name, token='', interval_time=0,
                                                   polling_limit=1)

    # then 서버와 연결된 볼륨 존재
    volumes = await cur_server.awaitable_attrs.volumes
    root_volume = volumes[0]
    assert isinstance(root_volume, Volume)

    # then 볼륨의 이름은 변경되지 않은 상태
    actual_db_volume = root_volume.__dict__
    actual_db_volume.pop('_sa_instance_state')
    expected_volume = volume_created.model_dump(exclude={'status'})
    assert actual_db_volume == expected_volume


@pytest.mark.asyncio
async def test_task_volume_extend_success(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                          test_db_session: AsyncSession, basic_volume: Volume):
    """
    test task_after_extend_volume
    1. 볼륨 확장 성공
    """
    # given
    cur_volume = basic_volume
    new_size = cur_volume.size + 10
    cur_volume.size = new_size
    # given volume service
    volume_service = VolumeService(volumeRepository=VolumeRepository(session=test_db_session))
    # given [MOCK] cinder 볼륨 정보 확인 (상태 AVAILABLE & 볼륨 용량 증가 완료)
    mocker.patch('backend.service.volume.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(cur_volume, VolumeStatus.AVAILABLE))

    # when
    await volume_service._task_after_extend_volume(volume=cur_volume, token='', interval_time=0, polling_limit=1)

    # then check db
    actual_volume = await test_db_session.scalar(select(Volume).filter(Volume.volume_id == cur_volume.volume_id))
    assert actual_volume.size == new_size


async def test_task_volume_extend_fail(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                       test_db_session: AsyncSession, basic_volume: Volume):
    """
    test task_after_extend_volume
    2. 볼륨 확장 실패
    """
    # given
    cur_volume = basic_volume
    # given volume service
    volume_service = VolumeService(volumeRepository=VolumeRepository(session=test_db_session))
    # given [MOCK] cinder 볼륨 정보 확인 (상태 error_extending & 볼륨 용량 증가 실패)
    mocker.patch('backend.service.volume.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(cur_volume,
                                                                                VolumeStatus.ERROR_EXTENDING))

    # when
    await volume_service._task_after_extend_volume(volume=cur_volume, token='', interval_time=0, polling_limit=1)

    # then check db
    actual_volume = await test_db_session.scalar(select(Volume).filter(Volume.volume_id == cur_volume.volume_id))
    assert actual_volume.size == cur_volume.size


async def test_task_volume_attach_success(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                          basic_server_with_root_volume,
                                          test_db_session: AsyncSession, basic_volume: Volume):
    """
    test task_after_attach_volume
    1. 볼륨  attach 성공시 db 확인
    """
    # given
    cur_server, _ = basic_server_with_root_volume
    cur_volume = basic_volume
    # given server service
    server_service = ServerService(volumeRepository=VolumeRepository(session=test_db_session),
                                   serverRepository=ServerRepository(session=test_db_session))
    # given [MOCK] CINDER : 볼륨 상태 IN_USE
    mocker.patch('backend.service.server.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(cur_volume, VolumeStatus.IN_USE))

    # when
    await server_service._task_after_attach_volume(server=cur_server, volume=cur_volume, token='', interval_time=0,
                                                   polling_limit=1)
    # then
    assert cur_volume.fk_server_id == cur_server.server_id
    assert cur_volume.is_root_volume == False


async def test_task_volume_attach_error(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                        basic_server_with_root_volume,
                                        test_db_session: AsyncSession, basic_volume: Volume):
    """
    test task_after_attach_volume
    2. 볼륨 attach 실패
    """
    # given
    cur_server, _ = basic_server_with_root_volume
    cur_volume = basic_volume
    # given server service
    server_service = ServerService(volumeRepository=VolumeRepository(session=test_db_session),
                                   serverRepository=ServerRepository(session=test_db_session))
    # given [MOCK] CINDER : 볼륨 상태 ERROR
    mocker.patch('backend.service.server.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(cur_volume, VolumeStatus.ERROR))

    # when
    await server_service._task_after_attach_volume(server=cur_server, volume=cur_volume, token='', interval_time=0,
                                                   polling_limit=1)
    # then
    assert cur_volume.fk_server_id is None


async def test_task_volume_detach_success(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                          all_connected_server: Server,
                                          test_db_session: AsyncSession):
    """
    test task_after_detach_volume
    1. 볼륨 detach 성공시 db 확인
    """
    # given
    cur_server = all_connected_server
    volumes = await cur_server.awaitable_attrs.volumes
    for volume in volumes:
        if not volume.is_root_volume:
            cur_volume = volume

    # given server service
    server_service = ServerService(volumeRepository=VolumeRepository(session=test_db_session),
                                   serverRepository=ServerRepository(session=test_db_session))

    # given [MOCK] CINDER: 볼륨 상태 AVAILABLE
    mocker.patch('backend.service.server.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(cur_volume, VolumeStatus.AVAILABLE))

    # when
    await server_service._task_after_detach_volume(volume=cur_volume, token='', interval_time=0,
                                                   polling_limit=1)

    # then
    assert cur_volume.fk_server_id is None


async def test_task_volume_detach_error(test_client_no_token: httpx.AsyncClient, mocker: MockFixture,
                                        all_connected_server: Server,
                                        test_db_session: AsyncSession):
    """
    test task_after_detach_volume
    2. 볼륨 detach 실패
    """
    # given
    cur_server = all_connected_server
    volumes = await cur_server.awaitable_attrs.volumes
    for volume in volumes:
        if not volume.is_root_volume:
            cur_volume = volume

    # given server service
    server_service = ServerService(volumeRepository=VolumeRepository(session=test_db_session),
                                   serverRepository=ServerRepository(session=test_db_session))

    # given [MOCK] CINDER: 볼륨 상태 ERROR
    mocker.patch('backend.service.server.cinder_client.show_volume_detail',
                 return_value=cinder_client_mock.show_volume_detail_with_status(cur_volume, VolumeStatus.ERROR))

    # when
    await server_service._task_after_detach_volume(volume=cur_volume, token='', interval_time=0,
                                                   polling_limit=1)

    # then
    assert cur_volume.fk_server_id == all_connected_server.server_id
