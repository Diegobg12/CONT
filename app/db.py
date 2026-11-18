from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        if url.startswith("sqlite:///"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args={"check_same_thread": False})
    return _engine


def set_engine(engine) -> None:
    """Para tests: usar otra BD."""
    global _engine
    _engine = engine


def init_db() -> None:
    from app import models  # noqa: F401  (registra las tablas)

    SQLModel.metadata.create_all(get_engine())


def get_session():
    with Session(get_engine()) as s:
        yield s
