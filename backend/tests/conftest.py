import os
import pytest
from sqlalchemy import Engine, event

from app.database import get_engine
from app.models import Base


@pytest.fixture(scope="session", autouse=True)
def persisted_metadata_database(tmp_path_factory: pytest.TempPathFactory):
    database_path = tmp_path_factory.mktemp("database") / "dataquay-tests.db"
    previous = os.environ.get("DATAQUAY_DATABASE_URL")
    os.environ["DATAQUAY_DATABASE_URL"] = f"sqlite+pysqlite:///{database_path}"
    engine = get_engine()
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()
    if previous is None:
        os.environ.pop("DATAQUAY_DATABASE_URL", None)
    else:
        os.environ["DATAQUAY_DATABASE_URL"] = previous


@pytest.fixture(autouse=True)
def clean_persisted_metadata(persisted_metadata_database: Engine):
    with persisted_metadata_database.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    yield


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
