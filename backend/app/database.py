from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DATAQUAY_DATABASE_URL_ENV = "DATAQUAY_DATABASE_URL"
BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Explicit process variables still win. Local files are loaded here so Alembic,
# tests, and the API resolve the database in the same way.
load_dotenv(BACKEND_ROOT / ".env.local", override=False)
load_dotenv(BACKEND_ROOT / ".env", override=False)


def get_database_url() -> str:
    database_url = os.getenv(DATAQUAY_DATABASE_URL_ENV, "").strip()
    if not database_url:
        raise RuntimeError(
            "DATAQUAY_DATABASE_URL is not configured. Set it in the backend "
            "environment or backend/.env."
        )
    return database_url


@lru_cache(maxsize=16)
def _engine_for_url(database_url: str) -> Engine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **options)


def get_engine() -> Engine:
    return _engine_for_url(get_database_url())


@lru_cache(maxsize=16)
def _session_factory_for_url(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(
        bind=_engine_for_url(database_url),
        autoflush=False,
        expire_on_commit=False,
    )


@contextmanager
def session_scope() -> Iterator[Session]:
    session = _session_factory_for_url(get_database_url())()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_database_engines() -> None:
    for engine in _known_engines():
        engine.dispose()
    _engine_for_url.cache_clear()
    _session_factory_for_url.cache_clear()


def _known_engines() -> tuple[Engine, ...]:
    # functools does not expose cached values; the active engine is sufficient for
    # test and process shutdown cleanup before caches are cleared.
    try:
        return (_engine_for_url(get_database_url()),)
    except Exception:
        return ()
