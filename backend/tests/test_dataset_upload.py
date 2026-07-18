from hashlib import sha256
from io import BytesIO
from pathlib import Path
import stat
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.database import session_scope
from app.main import app
from app.models import DatasetRecord, Workspace

client = TestClient(app)


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


def _zip_info_bytes(info: ZipInfo, content: bytes) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(info, content)
    return output.getvalue()


def _upload(
    archive: bytes,
    *,
    file_name: str = "field-study.zip",
    content_type: str = "application/zip",
):
    return client.post(
        "/api/datasets/upload",
        files={"file": (file_name, archive, content_type)},
    )


def test_upload_preserves_archive_and_originals_then_inspects_by_identifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "datasets"
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(storage_root))
    archive = _zip_bytes(
        {
            "participants.csv": (
                b"participant_id,value\nP001,10\nP002,20\n"
            ),
            "docs/README.md": b"# Field study\n",
        }
    )

    response = _upload(archive)

    assert response.status_code == 201
    upload = response.json()
    assert str(UUID(upload["dataset_id"])) == upload["dataset_id"]
    assert upload == {
        "dataset_id": upload["dataset_id"],
        "file_name": "field-study.zip",
        "dataset_name": "field-study",
        "archive_size_bytes": len(archive),
        "archive_checksum_sha256": sha256(archive).hexdigest(),
        "extracted_file_count": 2,
        "extracted_size_bytes": (
            len(b"participant_id,value\nP001,10\nP002,20\n")
            + len(b"# Field study\n")
        ),
        "inspection_url": f"/api/inspect/datasets/{upload['dataset_id']}",
    }

    workspace = storage_root / upload["dataset_id"]
    stored_archive = workspace / "archive" / "upload.zip"
    participants = workspace / "original" / "participants.csv"
    readme = workspace / "original" / "docs" / "README.md"
    assert stored_archive.read_bytes() == archive
    assert participants.read_bytes() == (
        b"participant_id,value\nP001,10\nP002,20\n"
    )
    assert readme.read_bytes() == b"# Field study\n"
    assert stored_archive.stat().st_mode & stat.S_IWUSR == 0
    assert participants.stat().st_mode & stat.S_IWUSR == 0
    assert readme.stat().st_mode & stat.S_IWUSR == 0

    original_before_inspection = {
        path.relative_to(workspace / "original"): path.read_bytes()
        for path in (workspace / "original").rglob("*")
        if path.is_file()
    }
    archive_before_inspection = stored_archive.read_bytes()
    inspection_response = client.get(upload["inspection_url"])

    assert inspection_response.status_code == 200
    inspection = inspection_response.json()
    assert inspection["summary"] == {
        "dataset_name": "field-study",
        "total_file_count": 2,
        "csv_file_count": 1,
        "total_size_bytes": upload["extracted_size_bytes"],
    }
    assert [file["relative_path"] for file in inspection["files"]] == [
        "docs/README.md",
        "participants.csv",
    ]
    assert inspection["files"][1]["csv_profile"]["row_count"] == 2
    assert {
        path.relative_to(workspace / "original"): path.read_bytes()
        for path in (workspace / "original").rglob("*")
        if path.is_file()
    } == original_before_inspection
    assert stored_archive.read_bytes() == archive_before_inspection

    audit_response = client.get(f"/api/audit/datasets/{upload['dataset_id']}")
    assert audit_response.status_code == 200
    events = audit_response.json()["events"]
    assert [event["action"] for event in events] == ["upload"]
    assert all(event["status"] == "success" for event in events)
    serialized_audit = audit_response.text
    assert "P001" not in serialized_audit
    assert "participant_id,value" not in serialized_audit


def test_upload_persists_parent_before_dataset_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "datasets"
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(storage_root))

    response = _upload(_zip_bytes({"data.csv": b"id,value\n1,2\n"}))

    assert response.status_code == 201
    dataset_id = UUID(response.json()["dataset_id"])
    with session_scope() as session:
        workspace = session.get(Workspace, dataset_id)
        dataset = session.get(DatasetRecord, dataset_id)
        assert workspace is not None
        assert dataset is not None
        assert dataset.workspace_id == workspace.id


def test_upload_persistence_failure_rolls_back_and_removes_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "datasets"
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(storage_root))

    def fail_dataset_insert(*_args) -> None:
        raise SQLAlchemyError("forced dataset metadata failure")

    event.listen(DatasetRecord, "before_insert", fail_dataset_insert)
    try:
        response = _upload(_zip_bytes({"data.csv": b"id,value\n1,2\n"}))
    finally:
        event.remove(DatasetRecord, "before_insert", fail_dataset_insert)

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "The dataset workspace metadata could not be persisted. "
        "Confirm that PostgreSQL is available and migrations are current."
    )
    assert storage_root.is_dir()
    assert list(storage_root.iterdir()) == []
    with session_scope() as session:
        assert session.scalar(select(func.count()).select_from(Workspace)) == 0
        assert session.scalar(select(func.count()).select_from(DatasetRecord)) == 0


@pytest.mark.parametrize(
    "member_name",
    ["../escape.csv", "folder/../../escape.csv", "..\\escape.csv", "/tmp.csv"],
)
def test_upload_rejects_archive_path_traversal(
    member_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "datasets"
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(storage_root))

    response = _upload(_zip_bytes({member_name: b"id,value\n1,2\n"}))

    assert response.status_code == 400
    assert "unsafe or traversing member path" in response.json()["detail"]
    assert not (tmp_path / "escape.csv").exists()
    assert not storage_root.exists() or list(storage_root.iterdir()) == []


def test_upload_rejects_non_zip_and_corrupt_uploads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "datasets"
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(storage_root))

    wrong_extension = _upload(b"plain text", file_name="dataset.csv")
    wrong_media_type = _upload(
        _zip_bytes({"data.csv": b"id\n1\n"}),
        content_type="text/plain",
    )
    corrupt_zip = _upload(b"not a zip")

    assert wrong_extension.status_code == 415
    assert wrong_media_type.status_code == 415
    assert corrupt_zip.status_code == 400
    assert "not a valid" in corrupt_zip.json()["detail"]
    assert not storage_root.exists() or list(storage_root.iterdir()) == []


@pytest.mark.parametrize("unsafe_kind", ["script", "executable", "symlink"])
def test_upload_rejects_unsupported_or_executable_archive_members(
    unsafe_kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "datasets"
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(storage_root))
    if unsafe_kind == "script":
        archive = _zip_bytes({"analysis.py": b"raise RuntimeError('must not run')\n"})
    else:
        info = ZipInfo("data.csv" if unsafe_kind == "executable" else "link.csv")
        info.create_system = 3
        mode = (
            stat.S_IFREG | 0o755
            if unsafe_kind == "executable"
            else stat.S_IFLNK | 0o777
        )
        info.external_attr = mode << 16
        archive = _zip_info_bytes(info, b"target")

    response = _upload(archive)

    assert response.status_code == 415
    assert not storage_root.exists() or list(storage_root.iterdir()) == []


def test_upload_rejects_compressed_and_extracted_size_over_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "datasets"
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(storage_root))
    archive = _zip_bytes({"data.csv": b"id,value\n1,1234567890\n"})

    monkeypatch.setattr(
        "app.services.dataset_workspace.MAX_UPLOAD_SIZE_BYTES",
        len(archive) - 1,
    )
    compressed_response = _upload(archive)
    assert compressed_response.status_code == 413

    monkeypatch.setattr(
        "app.services.dataset_workspace.MAX_UPLOAD_SIZE_BYTES",
        len(archive) + 1,
    )
    monkeypatch.setattr(
        "app.services.dataset_workspace.MAX_EXTRACTED_SIZE_BYTES",
        10,
    )
    extracted_response = _upload(archive)
    assert extracted_response.status_code == 413
    assert not storage_root.exists() or list(storage_root.iterdir()) == []


def test_identifier_inspection_returns_not_found_for_invalid_or_missing_dataset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATAQUAY_DATA_ROOT", str(tmp_path / "datasets"))

    invalid_response = client.get("/api/inspect/datasets/not-a-uuid")
    missing_response = client.get(
        "/api/inspect/datasets/00000000-0000-4000-8000-000000000000"
    )

    assert invalid_response.status_code == 404
    assert missing_response.status_code == 404
    assert invalid_response.json() == {"detail": "Dataset workspace was not found."}
