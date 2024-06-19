from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    SERVER_HOST: str
    SERVER_PORT: int
    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_USERNAME: str
    MYSQL_PASSWORD: str
    MYSQL_DATABASE: str
    MYSQL_TEST_DATABASE: str
    TEST_DB_URL: str = ''
    DB_URL: str = ''
    DB_ECHO_LOG_ENABLED: bool  # DB log를 활성화 시킬지 여부

    # openstack 관련
    OPENSTACK_ROOT_URL: str
    OPENSTACK_PROJECT_ID: str
    OPENSTACK_NEUTRON_PORT: int
    OPENSTACK_USERNAME: str
    OPENSTACK_PASSWORD: str
    OPENSTACK_PUBLIC_NETWORK_ID: str
    OPENSTACK_PRIVATE_NETWORK_ID: str
    OPENSTACK_SUBNET_ID: str
    OPENSTACK_DEFAULT_VOLUME_TYPE: str

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache()
def get_setting():
    settings = Settings()
    settings.TEST_DB_URL = f'mysql+aiomysql://{settings.MYSQL_USERNAME}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_TEST_DATABASE}'
    settings.DB_URL = f'mysql+aiomysql://{settings.MYSQL_USERNAME}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}'

    return settings
