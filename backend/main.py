import os

from backend.core.config import get_setting
from backend.app import create_app_with_db, read_yaml

SETTINGS = get_setting()

app = create_app_with_db(SETTINGS.DB_URL)

if __name__ == "__main__":
    import uvicorn

    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    loaded_log_config = read_yaml(ROOT_DIR + '/log_conf.yaml')
    uvicorn.run("main:app", host=SETTINGS.SERVER_HOST, port=SETTINGS.SERVER_PORT, log_config=loaded_log_config,
                reload=True)
