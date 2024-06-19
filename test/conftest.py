import uuid
from datetime import datetime
import pytest
import random
import string
import httpx
from asgi_lifespan import LifespanManager
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import create_app_with_db
from backend.core.config import get_setting
from backend.core.dependency import get_token_or_raise
from backend.model.floatingip import Floatingip
from backend.model.server import Server
from backend.model.volume import Volume
from backend.util.constant import USER_TOKEN_HEADER_FIELD
from backend.core.db import db, Database, Base

SETTINGS = get_setting()


def generate_string(length) -> str:
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string


def get_token_test(request: Request):
    """
    인증 token 검증을 거치지 않도록 하는 test dependency
    """
    token = request.cookies.get(USER_TOKEN_HEADER_FIELD)
    return token if token else generate_string(183)  # token length


@pytest.fixture(scope='session', autouse=True)
async def reset_test_db():
    """
    test 이전에 db를 초기화한다
    """
    db_ = Database()
    db_.init_db(SETTINGS.TEST_DB_URL)
    async with db_.engine.connect() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await db_.disconnect()


@pytest.fixture
async def test_client_no_token():
    """
    create test client (token을 랜덤값으로 생성하므로 별도 필요 없음)
    """
    app = create_app_with_db(db_url=SETTINGS.TEST_DB_URL)
    app.dependency_overrides[get_token_or_raise] = get_token_test
    async with LifespanManager(app):
        async with httpx.AsyncClient(app=app, base_url="http://test") as test_client_no_token:
            yield test_client_no_token


@pytest.fixture
async def test_client():
    """
    create test client
    """
    app = create_app_with_db(db_url=SETTINGS.TEST_DB_URL)
    async with LifespanManager(app):
        async with httpx.AsyncClient(app=app, base_url="http://test") as test_client:
            yield test_client


@pytest.fixture
async def test_db_session():
    async for db_session in db.get_db():
        yield db_session


@pytest.fixture
async def basic_floatingip(test_db_session: AsyncSession):
    """
    연결되지 않은 초기상태의 floatingip를 생성
    :return: floatingip
    """
    floatingip = Floatingip(
        floatingip_id=uuid.uuid4(),
        ip_address='321.321.321.321',
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_port_id=None,
        fk_network_id=uuid.UUID(SETTINGS.OPENSTACK_PUBLIC_NETWORK_ID),
        description='',
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0)
    )
    test_db_session.add(floatingip)
    await test_db_session.commit()
    yield floatingip


@pytest.fixture
async def deleted_floatingip(test_db_session: AsyncSession):
    """
    deleted 상태의 floatingip를 생성
    :return: floatingip
    """
    floatingip = Floatingip(
        floatingip_id=uuid.uuid4(),
        ip_address='321.321.321.321',
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_port_id=None,
        fk_network_id=uuid.UUID(SETTINGS.OPENSTACK_PUBLIC_NETWORK_ID),
        description='',
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0),
        deleted_at=datetime.now().replace(microsecond=0),
    )
    test_db_session.add(floatingip)
    await test_db_session.commit()
    yield floatingip


@pytest.fixture
async def basic_floatingip_with_server(test_db_session: AsyncSession):
    """
    floatingip와, floatingip에 연결된 server를 생성
    :return: floatingip, server
    """
    server = Server(
        server_id=uuid.uuid4(),
        name='server_with_floating_ip',
        description='server with floating ip',
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_flavor_id='1',
        fk_network_id=uuid.UUID(SETTINGS.OPENSTACK_PRIVATE_NETWORK_ID),
        fk_port_id=uuid.uuid4(),
        fixed_address='123.123.123.123',
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0),
        deleted_at=None,
    )
    test_db_session.add(server)
    floatingip = Floatingip(
        floatingip_id=uuid.uuid4(),
        ip_address='321.321.321.321',
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_port_id=server.fk_port_id,
        fk_network_id=uuid.UUID(SETTINGS.OPENSTACK_PUBLIC_NETWORK_ID),
        description='floatingip with port',
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0)
    )
    test_db_session.add(floatingip)
    await test_db_session.commit()
    yield floatingip, server


@pytest.fixture
async def basic_server(test_db_session: AsyncSession):
    """
    아무것도 연결되지 않은 서버를 리턴
    :return: server
    """
    server = Server(
        server_id=uuid.uuid4(),
        name='basic_server',
        description='no related entity',
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_flavor_id='1',
        fk_network_id=uuid.UUID(SETTINGS.OPENSTACK_PRIVATE_NETWORK_ID),
        fk_port_id=None,
        fixed_address=None,
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0),
        deleted_at=None,
    )
    test_db_session.add(server)
    await test_db_session.commit()
    yield server


@pytest.fixture
async def basic_server_with_port(test_db_session: AsyncSession):
    """
    아무것도 연결되지 않은 서버를 리턴
    :return: server
    """
    server = Server(
        server_id=uuid.uuid4(),
        name='basic_server',
        description='no related entity',
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_flavor_id='1',
        fk_network_id=uuid.UUID(SETTINGS.OPENSTACK_PRIVATE_NETWORK_ID),
        fk_port_id=uuid.uuid4(),
        fixed_address='321.321.321.312',
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0),
        deleted_at=None,
    )
    test_db_session.add(server)
    await test_db_session.commit()
    yield server


@pytest.fixture
async def basic_server_with_root_volume(test_db_session: AsyncSession):
    """
    root volume과 연결된 서버를 리턴
    :return: server, volume
    """
    server_id = uuid.uuid4()
    server = Server(
        server_id=server_id,
        name='basic_server_with_root_volume',
        description='',
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_flavor_id='1',
        fk_network_id=uuid.UUID(SETTINGS.OPENSTACK_PRIVATE_NETWORK_ID),
        fk_port_id=uuid.uuid4(),
        fixed_address='231.231.231.231',
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0),
        deleted_at=None,
    )
    volume = Volume(
        volume_id=uuid.uuid4(),
        name='basic_root_volume',
        description='',
        volume_type=SETTINGS.OPENSTACK_DEFAULT_VOLUME_TYPE,
        size=1,
        fk_server_id=server_id,
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_image_id=uuid.uuid4(),
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0),
        deleted_at=None,
    )
    test_db_session.add(server)
    test_db_session.add(volume)
    await test_db_session.commit()
    yield server, volume


@pytest.fixture
async def deleted_server(test_db_session: AsyncSession):
    server_id = uuid.uuid4()
    server = Server(
        server_id=server_id,
        name='deleted server',
        description='',
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_flavor_id='1',
        fk_network_id=uuid.UUID(SETTINGS.OPENSTACK_PRIVATE_NETWORK_ID),
        fk_port_id=None,
        fixed_address=None,
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0),
        deleted_at=datetime.now().replace(microsecond=0),
    )
    test_db_session.add(server)
    await test_db_session.commit()
    yield server


@pytest.fixture
async def all_connected_server(test_db_session: AsyncSession):
    """
    floating ip 1개
    root volume 1개
    기타 볼륨 3개
    연결된 서버
    """
    server_id = uuid.uuid4()
    server = Server(
        server_id=server_id,
        name='all_connected_server',
        description='all_connected_server',
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_flavor_id='1',
        fk_network_id=uuid.UUID(SETTINGS.OPENSTACK_PRIVATE_NETWORK_ID),
        fk_port_id=uuid.uuid4(),
        fixed_address='777.777.777.777',
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0),
        deleted_at=None,
    )
    test_db_session.add(server)
    root_volume = Volume(
        volume_id=uuid.uuid4(),
        name='root_volume',
        description='root volume',
        volume_type=SETTINGS.OPENSTACK_DEFAULT_VOLUME_TYPE,
        size=10,
        fk_server_id=server_id,
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_image_id=uuid.uuid4(),
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0),
        deleted_at=None,
    )
    test_db_session.add(root_volume)
    sub_volume = Volume(
        volume_id=uuid.uuid4(),
        name='sub_volume',
        description='sub volume',
        volume_type=SETTINGS.OPENSTACK_DEFAULT_VOLUME_TYPE,
        size=20,
        fk_server_id=server_id,
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_image_id=None,
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0),
        deleted_at=None,
    )
    test_db_session.add(sub_volume)
    floatingip = Floatingip(
        floatingip_id=uuid.uuid4(),
        ip_address='123.321.123.321',
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_port_id=server.fk_port_id,
        fk_network_id=uuid.UUID(SETTINGS.OPENSTACK_PUBLIC_NETWORK_ID),
        description='floatingip',
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0)
    )
    test_db_session.add(floatingip)
    await test_db_session.commit()
    yield server


@pytest.fixture
async def basic_volume(test_db_session: AsyncSession):
    """
    아무것도 연결되지 않은 빈 볼륨
    """
    volume = Volume(
        volume_id=uuid.uuid4(),
        name='basic_volume',
        description='basic volume',
        volume_type=SETTINGS.OPENSTACK_DEFAULT_VOLUME_TYPE,
        size=10,
        fk_server_id=None,
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_image_id=None,
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0),
        deleted_at=None,
    )
    test_db_session.add(volume)
    await test_db_session.commit()
    yield volume


@pytest.fixture
async def deleted_volume(test_db_session: AsyncSession):
    """
    삭제된 볼륨(연결 x)
    """
    volume = Volume(
        volume_id=uuid.uuid4(),
        name='deleted_volume',
        description='deleted volume',
        volume_type=SETTINGS.OPENSTACK_DEFAULT_VOLUME_TYPE,
        size=10,
        fk_server_id=None,
        fk_project_id=uuid.UUID(SETTINGS.OPENSTACK_PROJECT_ID),
        fk_image_id=None,
        created_at=datetime.now().replace(microsecond=0),
        updated_at=datetime.now().replace(microsecond=0),
        deleted_at=datetime.now().replace(microsecond=0),
    )
    test_db_session.add(volume)
    await test_db_session.commit()
    yield volume
