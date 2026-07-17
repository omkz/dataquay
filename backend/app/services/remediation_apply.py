from datetime import datetime
from hashlib import sha256
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile

import polars as pl

from app.schemas import (
    FileChecksumRecord,
    RemediationAction,
    RemediationActionResult,
    RemediationApplyResponse,
    RemediationChecksumManifest,
    RemediationOperation,
    RemediationRecommendation,
)
from app.services.dataset_inspector import inspect_dataset
from app.services.inspection_findings import DATE_FORMATS
from app.services.remediation_preview import preview_remediation_actions


class InvalidWorkingCopyPathError(ValueError):
    """Raised when a working-copy path could put source files at risk."""


def apply_approved_remediation_actions(
    approved_recommendations: list[RemediationRecommendation],
    source_directory: str | Path,
    working_copy_directory: str | Path,
) -> RemediationApplyResponse:
    """Apply approved deterministic actions to a refreshed working copy only."""
    source_root = Path(source_directory).resolve(strict=True)
    working_root = Path(working_copy_directory).resolve()
    _validate_working_copy_path(source_root, working_root)

    inspection = inspect_dataset(source_root)
    preview = preview_remediation_actions(
        approved_recommendations,
        inspection.findings,
    )
    get_checksum_manifest_path(working_root).unlink(missing_ok=True)
    _refresh_working_copy(source_root, working_root)

    applied_actions: list[RemediationActionResult] = []
    skipped_actions: list[RemediationActionResult] = []
    failed_actions: list[RemediationActionResult] = []

    for action in preview.actions:
        source_file = _resolve_dataset_file(source_root, action.target_file)
        output_file = _resolve_dataset_file(working_root, action.target_file)
        source_checksum = calculate_file_checksum(source_file)

        if not action.can_apply_automatically:
            skipped_actions.append(
                RemediationActionResult(
                    action=action,
                    source_checksum_sha256=source_checksum,
                    output_checksum_sha256=calculate_file_checksum(output_file),
                    message=(
                        "Skipped because this action requires manual review. "
                        f"{action.manual_review_reason}"
                    ),
                )
            )
            continue

        try:
            _apply_automatic_action(action, output_file)
        except Exception as exc:  # Keep independent actions isolated.
            failed_actions.append(
                RemediationActionResult(
                    action=action,
                    source_checksum_sha256=source_checksum,
                    output_checksum_sha256=(
                        calculate_file_checksum(output_file)
                        if output_file.is_file()
                        else None
                    ),
                    message=f"Action failed with {type(exc).__name__}.",
                )
            )
            continue

        applied_actions.append(
            RemediationActionResult(
                action=action,
                source_checksum_sha256=source_checksum,
                output_checksum_sha256=calculate_file_checksum(output_file),
                message="Action applied to the working copy.",
            )
        )

    file_checksums = _build_file_checksum_records(source_root, working_root)
    _write_checksum_manifest(
        RemediationChecksumManifest(
            source_directory=str(source_root),
            working_copy_directory=str(working_root),
            files=file_checksums,
        ),
        get_checksum_manifest_path(working_root),
    )

    return RemediationApplyResponse(
        working_copy_directory=str(working_root),
        applied_actions=applied_actions,
        skipped_actions=skipped_actions,
        failed_actions=failed_actions,
        file_checksums=file_checksums,
    )


def calculate_file_checksum(file_path: str | Path) -> str:
    """Calculate a SHA-256 checksum without loading the entire file into memory."""
    digest = sha256()
    with Path(file_path).open("rb") as file:
        for chunk in iter(lambda: file.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_checksum_manifest_path(working_copy_directory: str | Path) -> Path:
    working_root = Path(working_copy_directory).resolve()
    return working_root.parent / f"{working_root.name}.checksums.json"


def _validate_working_copy_path(source_root: Path, working_root: Path) -> None:
    filesystem_root = Path(working_root.anchor)
    paths_overlap = (
        source_root == working_root
        or source_root in working_root.parents
        or working_root in source_root.parents
    )
    if working_root == filesystem_root or paths_overlap:
        raise InvalidWorkingCopyPathError(
            "The working-copy directory must be separate from the source dataset."
        )


def _refresh_working_copy(source_root: Path, working_root: Path) -> None:
    if working_root.exists():
        shutil.rmtree(working_root)
    working_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_root, working_root)


def _resolve_dataset_file(dataset_root: Path, relative_path: str) -> Path:
    file_path = (dataset_root / relative_path).resolve(strict=True)
    if dataset_root not in file_path.parents or not file_path.is_file():
        raise ValueError(f"Target file is outside the dataset: '{relative_path}'.")
    return file_path


def _build_file_checksum_records(
    source_root: Path,
    working_root: Path,
) -> list[FileChecksumRecord]:
    records: list[FileChecksumRecord] = []
    for source_file in sorted(path for path in source_root.rglob("*") if path.is_file()):
        relative_path = source_file.relative_to(source_root)
        output_file = _resolve_dataset_file(working_root, relative_path.as_posix())
        records.append(
            FileChecksumRecord(
                relative_path=relative_path.as_posix(),
                source_checksum_sha256=calculate_file_checksum(source_file),
                output_checksum_sha256=calculate_file_checksum(output_file),
            )
        )
    return records


def _apply_automatic_action(action: RemediationAction, output_file: Path) -> None:
    data = pl.read_csv(output_file)

    match action.proposed_operation:
        case RemediationOperation.REMOVE_EXACT_DUPLICATE_ROWS:
            transformed = data.unique(maintain_order=True)
        case RemediationOperation.NORMALIZE_RECOGNIZED_DATE_FORMATS:
            if action.target_column is None or action.target_column not in data.columns:
                raise ValueError("The date-normalization target column is unavailable.")
            normalized_values = [
                _normalize_recognized_date(value)
                for value in data[action.target_column].to_list()
            ]
            transformed = data.with_columns(
                pl.Series(action.target_column, normalized_values, dtype=pl.String)
            )
        case _:
            raise ValueError(
                f"Operation '{action.proposed_operation.value}' is not automatic."
            )

    _write_csv_atomically(transformed, output_file)


def _normalize_recognized_date(value: object) -> object:
    if not isinstance(value, str):
        return value

    for _, date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue
    return value


def _write_csv_atomically(data: pl.DataFrame, output_file: Path) -> None:
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            dir=output_file.parent,
            prefix=f".{output_file.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
        data.write_csv(temporary_path)
        temporary_path.replace(output_file)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _write_checksum_manifest(
    manifest: RemediationChecksumManifest,
    manifest_path: Path,
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            dir=manifest_path.parent,
            prefix=f".{manifest_path.name}.",
            suffix=".tmp",
            mode="w",
            encoding="utf-8",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(manifest.model_dump_json(indent=2))
        temporary_path.replace(manifest_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
