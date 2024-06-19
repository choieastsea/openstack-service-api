from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncAttrs
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import get_setting

SETTINGS = get_setting()


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Database:
    """
    db와 관련한 설정을 담당하는 클래스

    session : AsyncSession 
    engine : AsyncEngine

    init_db시, DB_URL을 받아서 engine -> session을 초기화
    해당 파일의 db instance를 생성하여 사용할 수 있다.
    """

    def __init__(self):
        self.__session = None
        self.__engine = None

    @property
    def engine(self):
        return self.__engine

    def init_db(self, DB_URL: str):
        self.__engine = create_async_engine(
            DB_URL, echo=SETTINGS.DB_ECHO_LOG_ENABLED)

        self.__session = async_sessionmaker(
            bind=self.__engine,
            autocommit=False,
            expire_on_commit=False
        )

    async def disconnect(self):
        await self.__engine.dispose()

    async def get_db(self):
        async with self.__session() as session:
            try:
                yield session
            except SQLAlchemyError as err:
                await session.rollback()
                raise err
            finally:
                await session.close()


db = Database()
