from fastapi import FastAPI
from contextlib import asynccontextmanager
import yaml

from backend.core.config import get_setting
from backend.core.exception_handler import register_error_handlers
from backend.core.db import Base, db
from backend.api import api_router

SETTINGS = get_setting()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with db.engine.connect() as conn:
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await db.disconnect()


def create_app_with_db(db_url: str):
    """
    return fastapi app with db
    - db_url: url of database
    """
    app = FastAPI(lifespan=lifespan)
    db.init_db(db_url)
    app.include_router(
        api_router,
        prefix=""
    )
    register_error_handlers(app)
    return app


def read_yaml(path:str):
    # yaml 파일을 읽어와서 반환한다
    with open(path, 'rt') as f:
        loaded_log_config = yaml.safe_load(f.read())
    return loaded_log_config
