from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_and_downgrade_round_trip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATAQUAY_DATABASE_URL", database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert set(inspect(engine).get_table_names()) == {
        "alembic_version",
        "audit_events",
        "clarifications",
        "dataset_records",
        "human_decisions",
        "recommendation_batches",
        "recommendations",
        "sessions",
        "users",
        "verification_token",
        "workspaces",
    }
    assert "owner_id" in {
        column["name"] for column in inspect(engine).get_columns("workspaces")
    }

    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
