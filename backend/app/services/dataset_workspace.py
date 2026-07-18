import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile, ZipInfo

from fastapi import UploadFile
from pydantic import ValidationError

from app.api_errors import DatabaseError
from app.schemas import (
    AuditAction,
    AuditStatus,
    DatasetInspection,
    DatasetUploadResponse,
)
from app.services.audit_trail import append_audit_event
from app.services.dataset_inspector import inspect_dataset
from app.services.remediation_apply import calculate_file_checksum
from app.services.workflow_repository import (
    create_workspace_record,
    delete_workspace_record,
)

DATAQUAY_DATA_ROOT_ENV = "DATAQUAY_DATA_ROOT"
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024
MAX_EXTRACTED_SIZE_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 1_000
MAX_COMPRESSION_RATIO = 200
UPLOAD_CHUNK_SIZE = 64 * 1024
SUPPORTED_UPLOAD_CONTENT_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
}
SUPPORTED_DATA_EXTENSIONS = {
    ".csv",
    ".docx",
    ".json",
    ".jpeg",
    ".jpg",
    ".md",
    ".pdf",
    ".png",
    ".tsv",
    ".txt",
    ".xls",
    ".xlsx",
}
SUPPORTED_EXTENSIONLESS_FILES = {"codebook", "license", "readme"}


class DatasetUploadError(ValueError):
    """Base error for rejected local dataset uploads."""


class UnsupportedUploadError(DatasetUploadError):
    """Raised when an upload or archive member type is unsupported."""


class UploadTooLargeError(DatasetUploadError):
    """Raised when compressed or extracted size limits are exceeded."""


class UnsafeArchiveError(DatasetUploadError):
    """Raised when a ZIP cannot be extracted safely."""


class DatasetNotFoundError(LookupError):
    """Raised when a dataset identifier has no local workspace."""


def get_dataset_storage_root() -> Path:
    configured_root = os.getenv(DATAQUAY_DATA_ROOT_ENV, "").strip()
    if configured_root:
        return Path(configured_root).expanduser().resolve()
    return (Path(__file__).resolve().parents[2] / ".dataquay" / "datasets").resolve()


async def create_dataset_workspace(
    upload: UploadFile,
    *,
    storage_root: str | Path | None = None,
) -> DatasetUploadResponse:
    """Persist and safely extract one untrusted ZIP into an isolated workspace."""
    file_name = _validate_upload_metadata(upload)
    root = Path(storage_root).resolve() if storage_root is not None else get_dataset_storage_root()
    root.mkdir(parents=True, exist_ok=True)

    dataset_id = str(uuid4())
    staging_root = root / f".upload-{dataset_id}"
    final_root = root / dataset_id
    archive_directory = staging_root / "archive"
    original_directory = staging_root / "original"
    archive_path = archive_directory / "upload.zip"
    archive_directory.mkdir(parents=True)
    original_directory.mkdir()

    try:
        archive_size = await _stream_upload(upload, archive_path)
        extracted_file_count, extracted_size = _extract_archive_safely(
            archive_path,
            original_directory,
        )
        archive_checksum = calculate_file_checksum(archive_path)
        response = DatasetUploadResponse(
            dataset_id=dataset_id,
            file_name=file_name,
            dataset_name=_dataset_name_from_file(file_name),
            archive_size_bytes=archive_size,
            archive_checksum_sha256=archive_checksum,
            extracted_file_count=extracted_file_count,
            extracted_size_bytes=extracted_size,
            inspection_url=f"/api/inspect/datasets/{dataset_id}",
        )
        (staging_root / "metadata.json").write_text(
            json.dumps(response.model_dump(mode="json"), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        archive_path.chmod(0o444)
        for extracted_file in original_directory.rglob("*"):
            if extracted_file.is_file():
                extracted_file.chmod(0o444)
        staging_root.replace(final_root)
        try:
            create_workspace_record(response, storage_path=str(final_root))
            append_audit_event(
                final_root,
                dataset_id=dataset_id,
                action=AuditAction.UPLOAD,
                status=AuditStatus.SUCCESS,
                summary=(
                    f"Dataset archive accepted with {extracted_file_count} extracted "
                    f"files totaling {extracted_size} bytes."
                ),
            )
        except Exception:
            try:
                delete_workspace_record(dataset_id)
            except DatabaseError:
                pass
            shutil.rmtree(final_root, ignore_errors=True)
            raise
        return response
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise


def inspect_dataset_workspace(
    dataset_id: str,
    *,
    storage_root: str | Path | None = None,
) -> DatasetInspection:
    workspace, metadata = resolve_dataset_workspace(
        dataset_id,
        storage_root=storage_root,
    )
    inspection = inspect_dataset(workspace / "original")
    return inspection.model_copy(
        update={
            "summary": inspection.summary.model_copy(
                update={"dataset_name": metadata.dataset_name}
            )
        }
    )


def resolve_dataset_workspace(
    dataset_id: str,
    *,
    storage_root: str | Path | None = None,
) -> tuple[Path, DatasetUploadResponse]:
    root = Path(storage_root).resolve() if storage_root is not None else get_dataset_storage_root()
    try:
        parsed_id = UUID(dataset_id)
    except ValueError as exc:
        raise DatasetNotFoundError("Dataset workspace was not found.") from exc
    if str(parsed_id) != dataset_id:
        raise DatasetNotFoundError("Dataset workspace was not found.")

    workspace = (root / dataset_id).resolve()
    if root not in workspace.parents or not workspace.is_dir():
        raise DatasetNotFoundError("Dataset workspace was not found.")
    try:
        metadata = DatasetUploadResponse.model_validate_json(
            (workspace / "metadata.json").read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        raise DatasetNotFoundError("Dataset workspace metadata is unavailable.") from exc
    if metadata.dataset_id != dataset_id or not (workspace / "original").is_dir():
        raise DatasetNotFoundError("Dataset workspace is invalid.")
    return workspace, metadata


def _validate_upload_metadata(upload: UploadFile) -> str:
    raw_name = (upload.filename or "").replace("\\", "/")
    file_name = raw_name.rsplit("/", maxsplit=1)[-1]
    if not file_name or Path(file_name).suffix.lower() != ".zip":
        raise UnsupportedUploadError("Only ZIP dataset uploads are supported.")
    content_type = (upload.content_type or "").split(";", maxsplit=1)[0].lower()
    if content_type not in SUPPORTED_UPLOAD_CONTENT_TYPES:
        raise UnsupportedUploadError(
            "The upload content type is not supported; provide a ZIP file."
        )
    return file_name


async def _stream_upload(upload: UploadFile, archive_path: Path) -> int:
    size = 0
    with archive_path.open("xb") as destination:
        while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE_BYTES:
                raise UploadTooLargeError(
                    f"ZIP uploads must not exceed {MAX_UPLOAD_SIZE_BYTES} bytes."
                )
            destination.write(chunk)
    if size == 0:
        raise UnsafeArchiveError("The uploaded ZIP file is empty.")
    return size


def _extract_archive_safely(
    archive_path: Path,
    original_directory: Path,
) -> tuple[int, int]:
    try:
        with ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_ENTRIES:
                raise UploadTooLargeError(
                    f"ZIP archives may contain at most {MAX_ARCHIVE_ENTRIES} entries."
                )

            planned_members = _validate_archive_members(members)
            extracted_file_count = 0
            extracted_size = 0
            for member, relative_path in planned_members:
                destination = (original_directory / relative_path).resolve()
                if original_directory not in destination.parents:
                    raise UnsafeArchiveError(
                        "The ZIP contains a path outside the dataset workspace."
                    )
                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue

                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open("xb") as output:
                    while chunk := source.read(UPLOAD_CHUNK_SIZE):
                        extracted_size += len(chunk)
                        if extracted_size > MAX_EXTRACTED_SIZE_BYTES:
                            raise UploadTooLargeError(
                                "The extracted dataset exceeds the allowed size."
                            )
                        output.write(chunk)
                extracted_file_count += 1

            if extracted_file_count == 0:
                raise UnsafeArchiveError(
                    "The ZIP does not contain any supported dataset files."
                )
            return extracted_file_count, extracted_size
    except BadZipFile as exc:
        raise UnsafeArchiveError(
            "The uploaded file is not a valid, readable ZIP archive."
        ) from exc
    except OSError as exc:
        raise UnsafeArchiveError("The ZIP archive could not be extracted safely.") from exc


def _validate_archive_members(
    members: list[ZipInfo],
) -> list[tuple[ZipInfo, Path]]:
    total_size = 0
    normalized_paths: set[str] = set()
    planned_members: list[tuple[ZipInfo, Path]] = []

    for member in members:
        relative_path = _safe_member_path(member)
        normalized_key = relative_path.as_posix().casefold()
        if normalized_key in normalized_paths:
            raise UnsafeArchiveError(
                "The ZIP contains duplicate or conflicting member paths."
            )
        normalized_paths.add(normalized_key)
        _validate_member_type(member, relative_path)

        if not member.is_dir():
            total_size += member.file_size
            if total_size > MAX_EXTRACTED_SIZE_BYTES:
                raise UploadTooLargeError(
                    "The extracted dataset exceeds the allowed size."
                )
            if (
                member.file_size > 1024 * 1024
                and member.file_size
                > max(member.compress_size, 1) * MAX_COMPRESSION_RATIO
            ):
                raise UploadTooLargeError(
                    "The ZIP contains an unsafe compression ratio."
                )
        planned_members.append((member, relative_path))
    return planned_members


def _safe_member_path(member: ZipInfo) -> Path:
    normalized_name = member.filename.replace("\\", "/")
    if not normalized_name or len(normalized_name) > 1024:
        raise UnsafeArchiveError("The ZIP contains an invalid member path.")
    raw_parts = normalized_name.split("/")
    if member.is_dir() and raw_parts[-1] == "":
        raw_parts = raw_parts[:-1]
    if (
        not raw_parts
        or normalized_name.startswith("/")
        or any(part in {"", ".", ".."} for part in raw_parts)
        or raw_parts[0].endswith(":")
    ):
        raise UnsafeArchiveError(
            "The ZIP contains an unsafe or traversing member path."
        )
    pure_path = PurePosixPath(*raw_parts)
    if pure_path.is_absolute():
        raise UnsafeArchiveError(
            "The ZIP contains an unsafe or traversing member path."
        )
    return Path(*pure_path.parts)


def _validate_member_type(member: ZipInfo, relative_path: Path) -> None:
    if member.flag_bits & 0x1:
        raise UnsupportedUploadError("Encrypted ZIP entries are not supported.")
    unix_mode = (member.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(unix_mode)
    if stat.S_ISLNK(unix_mode) or file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise UnsupportedUploadError(
            "Links and special files are not supported in dataset ZIPs."
        )
    if not member.is_dir() and unix_mode & 0o111:
        raise UnsupportedUploadError(
            "Executable files are not supported in dataset ZIPs."
        )
    if member.is_dir():
        return

    extension = relative_path.suffix.lower()
    if (
        extension not in SUPPORTED_DATA_EXTENSIONS
        and relative_path.name.casefold() not in SUPPORTED_EXTENSIONLESS_FILES
    ):
        raise UnsupportedUploadError(
            f"Unsupported dataset file type: '{extension or 'no extension'}'."
        )


def _dataset_name_from_file(file_name: str) -> str:
    dataset_name = Path(file_name).stem.strip()
    return dataset_name[:120] or "uploaded-dataset"
