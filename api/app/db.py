from pathlib import Path
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import PROJECT_ROOT, get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
Path(PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)
engine = create_engine(
    settings.resolved_database_url,
    connect_args={"check_same_thread": False, "timeout": 30} if settings.resolved_database_url.startswith("sqlite") else {},
    pool_pre_ping=True,
)

if settings.resolved_database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
