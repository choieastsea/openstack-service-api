from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.client.base import BaseClient
from backend.core.db import db
from backend.schema.oa_base import OpenstackBaseRequest

router = APIRouter(prefix="/healthcheck", tags=["healthcheck"])


@router.get('/')
async def health_check(session: AsyncSession = Depends(db.get_db)):
    """
    perform health check
    1. db session
    2. openstack api
    """
    response = await session.scalar(text('SELECT SQL_NO_CACHE 1;'))
    assert response == 1
    oa_request = OpenstackBaseRequest(url='/identity/v3')
    await BaseClient().request_openstack('GET', oa_request)
    return {'status': 'ok'}
