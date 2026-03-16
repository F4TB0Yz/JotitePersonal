import json
import os
import time as _time
from sqlalchemy.orm import Session
from src.infrastructure.database.models import ConfigORM

_config_cache: "dict | None" = None
_config_cache_ts: float = 0.0


class ConfigRepository:
    def __init__(self, session: Session, config_path: str = "config.json"):
        self.session = session
        self.config_path = config_path

    @classmethod
    def get_cached(cls, ttl: int = 300) -> dict:
        """Return J&T config from a TTL cache (default 5 min).
        Self-manages its DB session — guaranteed no leaks.
        """
        global _config_cache, _config_cache_ts
        if _config_cache is not None and (_time.monotonic() - _config_cache_ts) < ttl:
            return _config_cache
        from src.infrastructure.database.connection import SessionLocal
        s = SessionLocal()
        try:
            cfg = cls(s).load_config()
        finally:
            s.close()
        _config_cache = cfg
        _config_cache_ts = _time.monotonic()
        return cfg

    def load_config(self) -> dict:
        config = {
            "baseUrl": "https://gw.jtexpress.co/operatingplatform",
            "lang": "es",
            "home_network_id": "1009",
            "home_network_name": "Cund-Punto6"
        }

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                    config.update(file_config)
            except json.JSONDecodeError:
                # Optionally log or raise a domain exception here
                pass

        try:
            token_record = self.session.query(ConfigORM).filter_by(key="authToken").first()
            if token_record:
                config["authToken"] = token_record.value
        except Exception:
            # Optionally log or raise a domain exception here
            pass

        return config

    @classmethod
    def clear_cache(cls):
        """Limpia el caché global de configuración."""
        global _config_cache
        _config_cache = None

    def set_key(self, key: str, value: str):
        """Guarda o actualiza una llave en ConfigORM y limpia el caché."""
        record = self.session.query(ConfigORM).filter_by(key=key).first()
        if record:
            record.value = value
        else:
            record = ConfigORM(key=key, value=value)
            self.session.add(record)
        self.session.commit()
        self.__class__.clear_cache()
