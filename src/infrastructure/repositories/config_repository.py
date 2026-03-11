import json
import os
from sqlalchemy.orm import Session
from src.infrastructure.database.models import ConfigORM

class ConfigRepository:
    def __init__(self, session: Session, config_path: str = "config.json"):
        self.session = session
        self.config_path = config_path

    def load_config(self) -> dict:
        config = {
            "baseUrl": "https://gw.jtexpress.co/operatingplatform",
            "lang": "es"
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
