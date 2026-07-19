from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import os
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url

from app.database import dispose_database_engines, session_scope
from app.main import app
from app.models import RecommendationBatch, User
from app.schemas import RecommendationResponse
from app.services.workflow_repository import save_recommendation_batch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DATASET_PATH = BACKEND_ROOT.parent / "sample-data" / "soil-study"


@pytest.mark.postgresql
def test_postgresql_workflow_persists_and_reopens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _postgresql_test_url()
    schema = f"dataquay_test_{uuid4().hex}"
    admin_engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    scoped_url = make_url(database_url).set(
        query={**dict(make_url(database_url).query), "options": f"-csearch_path={schema}"}
    )
    monkeypatch.setenv("DATAQUAY_DATABASE_URL", scoped_url.render_as_string(hide_password=False))
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(tmp_path / "datasets"))
    dispose_database_engines()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    verification_engine = create_engine(scoped_url)

    try:
        command.upgrade(config, "head")
        assert set(inspect(verification_engine).get_table_names()) == {
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
        with verification_engine.begin() as connection:
            connection.execute(
                User.__table__.insert().values(
                    id=1,
                    email="postgres-steward@example.test",
                )
            )
        client = TestClient(app)
        upload = client.post(
            "/api/datasets/upload",
            files={
                "file": (
                    "postgres-workflow.zip",
                    _sample_archive(),
                    "application/zip",
                )
            },
        )
        assert upload.status_code == 201
        dataset_id = upload.json()["dataset_id"]

        inspection = client.get(f"/api/inspect/datasets/{dataset_id}")
        assert inspection.status_code == 200
        clarifications = client.get(f"/api/clarify/datasets/{dataset_id}")
        assert clarifications.status_code == 200
        question = clarifications.json()["questions"][0]
        answer = client.put(
            f"/api/clarify/datasets/{dataset_id}/questions/{question['question_id']}",
            json={"decision": "answer", "answer": "Confirmed study context."},
        )
        assert answer.status_code == 200

        recommendation_response = _recommendation_response()

        async def fake_recommendations(_inspection, *, clarifications):
            assert clarifications.summary.answered_count == 1
            return recommendation_response

        monkeypatch.setattr(
            "app.routes.inspect.generate_recommendations",
            fake_recommendations,
        )
        recommendations = client.post(
            f"/api/inspect/datasets/{dataset_id}/recommendations"
        )
        assert recommendations.status_code == 200
        approval = client.put(
            f"/api/workspaces/{dataset_id}/decision",
            json={"recommendation_key": "recommendation-0", "decision": "approved"},
        )
        assert approval.status_code == 200

        dispose_database_engines()
        reopened = TestClient(app).get(f"/api/workspaces/{dataset_id}")
        assert reopened.status_code == 200
        assert reopened.json()["workflow_status"] == "in_review"
        assert reopened.json()["decisions"] == {"recommendation-0": "approved"}
        assert reopened.json()["recommendations"][0]["short_title"] == (
            "Document expected missingness"
        )
        reopened_clarifications = TestClient(app).get(
            f"/api/clarify/datasets/{dataset_id}"
        )
        assert reopened_clarifications.status_code == 200
        assert reopened_clarifications.json()["summary"]["answered_count"] == 1
        audit = TestClient(app).get(f"/api/audit/datasets/{dataset_id}")
        assert [event["action"] for event in audit.json()["events"]] == [
            "upload",
            "clarification_response",
            "recommendation_generation",
            "human_decision",
        ]

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    save_recommendation_batch,
                    dataset_id,
                    recommendation_response,
                )
                for _ in range(2)
            ]
            for future in futures:
                future.result()
        with session_scope() as session:
            generations = session.scalars(
                select(RecommendationBatch.generation).order_by(
                    RecommendationBatch.generation
                )
            ).all()
        assert generations == [1, 2, 3]

        command.downgrade(config, "base")
        assert inspect(verification_engine).get_table_names() == ["alembic_version"]
    finally:
        dispose_database_engines()
        verification_engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def _postgresql_test_url() -> str:
    configured = os.getenv("DATAQUAY_TEST_DATABASE_URL")
    if not configured:
        configured = dotenv_values(BACKEND_ROOT / ".env").get(
            "DATAQUAY_DATABASE_URL"
        )
    if not configured or make_url(str(configured)).get_backend_name() != "postgresql":
        pytest.skip(
            "Set DATAQUAY_TEST_DATABASE_URL or backend/.env to run PostgreSQL integration tests."
        )
    return str(configured)


def _sample_archive() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(SAMPLE_DATASET_PATH.rglob("*")):
            if path.is_file():
                archive.writestr(
                    path.relative_to(SAMPLE_DATASET_PATH).as_posix(),
                    path.read_bytes(),
                )
    return output.getvalue()


def _recommendation_response() -> RecommendationResponse:
    return RecommendationResponse.model_validate(
        {
            "recommendations": [
                {
                    "related_finding": {
                        "type": "missing_values",
                        "file": "participants.csv",
                        "affected_column": "email",
                    },
                    "short_title": "Document expected missingness",
                    "rationale": "The confirmed context explains this missingness.",
                    "proposed_action": "Document the missing-value convention.",
                    "confidence": 0.92,
                    "human_approval_required": True,
                    "assumptions": [],
                }
            ]
        }
    )
