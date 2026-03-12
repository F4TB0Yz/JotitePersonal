import logging

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from .config import DEFAULT_DATABASE_URL, get_database_url
from .models import Base
from .migrations import run_all_migrations


logger = logging.getLogger(__name__)


_engine = create_engine(get_database_url(), future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False)
SessionLocal.configure(bind=_engine)

_db_initialized = False


def _switch_to_default_sqlite() -> None:
    global _engine
    _engine = create_engine(DEFAULT_DATABASE_URL, future=True)
    SessionLocal.configure(bind=_engine)


def initialize_database() -> None:
    global _db_initialized
    if _db_initialized:
        return
    try:
        Base.metadata.create_all(bind=_engine)
        run_all_migrations(_engine)
        _db_initialized = True
    except SQLAlchemyError as exc:
        logger.warning(
            "No se pudo conectar a la base de datos configurada (%s). Usando SQLite fallback. Error: %s",
            get_database_url(),
            exc,
        )
        _switch_to_default_sqlite()
        Base.metadata.create_all(bind=_engine)
        run_all_migrations(_engine)
        _db_initialized = True
