from io import BytesIO
import time
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
import jwt
import pytest

from app.auth import TOKEN_AUDIENCE, TOKEN_ISSUER, require_authenticated_user
from app.database import session_scope
from app.main import app
from app.models import User, Workspace

TEST_SECRET = "test-only-internal-identity-secret-32-bytes"


def _token(
    user_id: int,
    *,
    secret: str = TEST_SECRET,
    issued_at: int | None = None,
    expires_at: int | None = None,
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": str(user_id),
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
            "iat": issued_at if issued_at is not None else now,
            "exp": expires_at if expires_at is not None else now + 60,
        },
        secret,
        algorithm="HS256",
    )


def _auth_header(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id)}"}


def _archive() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("participants.csv", "participant_id,value\nP001,10\n")
    return output.getvalue()


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        f"Bearer {_token(1, secret='different-test-signing-secret-32-bytes')}",
        f"Bearer {_token(1, issued_at=int(time.time()) - 70, expires_at=int(time.time()) - 10)}",
    ],
)
def test_protected_api_rejects_missing_invalid_and_expired_credentials(
    authorization: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides.pop(require_authenticated_user, None)
    monkeypatch.setenv("DATAQUAY_INTERNAL_AUTH_SECRET", TEST_SECRET)
    headers = {"Authorization": authorization} if authorization else {}

    response = TestClient(app).get("/api/workspaces", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "A valid authenticated identity is required."}
    assert response.headers["www-authenticate"] == "Bearer"


def test_missing_internal_identity_configuration_returns_structured_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides.pop(require_authenticated_user, None)
    monkeypatch.delenv("DATAQUAY_INTERNAL_AUTH_SECRET", raising=False)

    response = TestClient(app).get("/api/workspaces")

    assert response.status_code == 503
    assert response.json()["code"] == "auth_not_configured"


def test_health_check_remains_public(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides.pop(require_authenticated_user, None)
    monkeypatch.delenv("DATAQUAY_INTERNAL_AUTH_SECRET", raising=False)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_assigns_owner_and_other_users_cannot_discover_workspace(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides.pop(require_authenticated_user, None)
    monkeypatch.setenv("DATAQUAY_INTERNAL_AUTH_SECRET", TEST_SECRET)
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(tmp_path / "datasets"))
    with session_scope() as session:
        session.add(User(id=2, email="another-steward@example.test"))

    client = TestClient(app)
    upload = client.post(
        "/api/datasets/upload",
        headers=_auth_header(1),
        files={"file": ("owned-study.zip", _archive(), "application/zip")},
    )

    assert upload.status_code == 201
    dataset_id = upload.json()["dataset_id"]
    with session_scope() as session:
        workspace = session.get(Workspace, UUID(dataset_id))
        assert workspace is not None
        assert workspace.owner_id == 1

    isolated_requests = (
        ("GET", f"/api/workspaces/{dataset_id}", None),
        ("GET", f"/api/inspect/datasets/{dataset_id}", None),
        ("POST", f"/api/inspect/datasets/{dataset_id}/recommendations", None),
        ("GET", f"/api/clarify/datasets/{dataset_id}", None),
        (
            "PUT",
            f"/api/clarify/datasets/{dataset_id}/questions/cq_00000000000000000000",
            {"decision": "defer"},
        ),
        (
            "PUT",
            f"/api/workspaces/{dataset_id}/decision",
            {"recommendation_key": "recommendation-0", "decision": "approved"},
        ),
        (
            "POST",
            f"/api/remediate/datasets/{dataset_id}/preview",
            {"approved_recommendations": []},
        ),
        (
            "POST",
            f"/api/remediate/datasets/{dataset_id}/apply",
            {"approved_recommendations": []},
        ),
        ("POST", f"/api/validate/datasets/{dataset_id}", None),
        ("POST", f"/api/package/datasets/{dataset_id}", None),
        ("GET", f"/api/package/datasets/{dataset_id}/download", None),
        ("GET", f"/api/audit/datasets/{dataset_id}", None),
    )
    for method, path, payload in isolated_requests:
        response = client.request(
            method,
            path,
            headers=_auth_header(2),
            json=payload,
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Dataset workspace was not found."}
    assert client.get("/api/workspaces", headers=_auth_header(2)).json() == {
        "workspaces": []
    }

    # Rows created before ownership was introduced remain intentionally inaccessible.
    with session_scope() as session:
        workspace = session.get(Workspace, UUID(dataset_id))
        assert workspace is not None
        workspace.owner_id = None
    assert client.get(
        f"/api/workspaces/{dataset_id}", headers=_auth_header(1)
    ).status_code == 404
    assert client.get("/api/workspaces", headers=_auth_header(1)).json() == {
        "workspaces": []
    }
