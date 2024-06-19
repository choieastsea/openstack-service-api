import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.model.server import Server
from backend.repository.server import ServerRepository


async def test_find_by_name(test_client_no_token: httpx.AsyncClient, basic_server: Server,
                            test_db_session: AsyncSession):
    """
    정상 경우 조회 가능
    """
    serverRepository = ServerRepository(session=test_db_session)
    server = await serverRepository.find_server_by_name(name=basic_server.name)
    assert isinstance(server, Server)


async def test_find_deleted_by_name(test_client_no_token: httpx.AsyncClient, deleted_server: Server,
                                    test_db_session: AsyncSession):
    """
    삭제된 경우, check_alive=True면 x
    """
    serverRepository = ServerRepository(session=test_db_session)
    server = await serverRepository.find_server_by_name(name=deleted_server.name, check_alive=True)
    assert server is None
