import json
import os
from functools import lru_cache


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEFAULT_SQLITE_PATH = os.path.join(PROJECT_ROOT, "data", "novedades.db")
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH}"


@lru_cache(maxsize=1)
def get_database_url() -> str:
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        if env_url.startswith("postgres://"):
            env_url = env_url.replace("postgres://", "postgresql://", 1)
        return env_url

    config_path = os.path.join(PROJECT_ROOT, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            db_url = data.get("database_url")
            if db_url:
                return db_url
        except Exception:
            pass

    return DEFAULT_DATABASE_URL
