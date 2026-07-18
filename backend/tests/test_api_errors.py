import os

from fastapi.testclient import TestClient

from app.database import dispose_database_engines
from app.main import app

client = TestClient(app)


def test_missing_database_configuration_returns_structured_503() -> None:
    original = os.environ.pop("DATAQUAY_DATABASE_URL", None)
    dispose_database_engines()
    try:
        response = client.get("/api/workspaces")
    finally:
        if original is not None:
            os.environ["DATAQUAY_DATABASE_URL"] = original
        dispose_database_engines()

    assert response.status_code == 503
    assert response.json() == {
        "code": "database_not_configured",
        "detail": (
            "DATAQUAY_DATABASE_URL is not configured. Set it in the backend "
            "environment or backend/.env."
        ),
    }


def test_postgresql_connection_failure_returns_structured_503() -> None:
    original = os.environ.get("DATAQUAY_DATABASE_URL")
    os.environ["DATAQUAY_DATABASE_URL"] = (
        "postgresql+psycopg://invalid@127.0.0.1:1/dataquay?connect_timeout=1"
    )
    dispose_database_engines()
    try:
        response = client.get("/api/workspaces")
    finally:
        if original is None:
            os.environ.pop("DATAQUAY_DATABASE_URL", None)
        else:
            os.environ["DATAQUAY_DATABASE_URL"] = original
        dispose_database_engines()

    assert response.status_code == 503
    assert response.json() == {
        "code": "database_unavailable",
        "detail": (
            "Workspace metadata is unavailable. Confirm that PostgreSQL is running "
            "and apply the latest Alembic migration."
        ),
    }
