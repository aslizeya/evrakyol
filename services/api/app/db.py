from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL tanımlı değil")
    # Kısa bağlantı zaman aşımı: veritabanı yoksa istekler (ör. /health) uzun süre asılı kalmasın.
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


def get_session() -> Iterator[Session]:
    """FastAPI bağımlılığı: istek başına bir veritabanı oturumu."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)
