import pytest
import httpx
from pytest_mock import MockFixture

from backend.client.base import BaseClient


@pytest.mark.asyncio
async def test_health_check(test_client: httpx.AsyncClient, mocker: MockFixture):
    """
    test healthcheck api
    * 200 : 정상적으로 서버가 실행
    """
    # given
    mocker.patch.object(BaseClient, 'request_openstack', return_value=True)
    # when
    response = await test_client.get("/api/healthcheck/")
    # then
    assert response.status_code == 200
