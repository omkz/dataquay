from pathlib import Path

from pydantic import ValidationError

from app.schemas import (
    DatasetValidationResult,
    FileChecksumRecord,
    FileChecksumVerification,
    FindingReference,
    InspectionFinding,
    RemediationChecksumManifest,
)
from app.services.dataset_inspector import inspect_dataset
from app.services.remediation_apply import (
    calculate_file_checksum,
    get_checksum_manifest_path,
)


class ValidationUnavailableError(RuntimeError):
    """Raised when no valid applied working copy is available to validate."""


def validate_remediated_dataset(
    source_directory: str | Path,
    working_copy_directory: str | Path,
) -> DatasetValidationResult:
    """Reinspect a working copy and verify it against apply-time provenance."""
    source_root = Path(source_directory).resolve(strict=True)
    working_root = Path(working_copy_directory).resolve()
    if not working_root.is_dir():
        raise ValidationUnavailableError(
            "The remediated working copy does not exist; apply remediation first."
        )

    manifest = load_checksum_manifest(working_root)
    if (
        manifest.source_directory != str(source_root)
        or manifest.working_copy_directory != str(working_root)
    ):
        raise ValidationUnavailableError(
            "The checksum manifest does not match the requested dataset paths."
        )

    before = inspect_dataset(source_root)
    after = inspect_dataset(working_root)
    checksum_verifications = _verify_file_checksums(
        source_root,
        working_root,
        manifest.files,
    )
    after_finding_keys = {_finding_key(finding) for finding in after.findings}
    resolved_findings = [
        finding
        for finding in before.findings
        if _finding_key(finding) not in after_finding_keys
    ]
    source_checksums_verified = all(
        verification.source_checksum_verified
        for verification in checksum_verifications
    )
    output_checksums_verified = all(
        verification.output_checksum_verified
        for verification in checksum_verifications
    )

    return DatasetValidationResult(
        resolved_findings=resolved_findings,
        remaining_findings=after.findings,
        checksum_verifications=checksum_verifications,
        source_checksums_verified=source_checksums_verified,
        output_checksums_verified=output_checksums_verified,
        original_files_unchanged=source_checksums_verified,
        readiness=after.readiness,
    )


def load_checksum_manifest(
    working_copy_directory: str | Path,
) -> RemediationChecksumManifest:
    working_root = Path(working_copy_directory).resolve()
    manifest_path = get_checksum_manifest_path(working_root)
    try:
        manifest_content = manifest_path.read_text(encoding="utf-8")
        return RemediationChecksumManifest.model_validate_json(manifest_content)
    except (OSError, ValidationError) as exc:
        raise ValidationUnavailableError(
            "The remediation checksum manifest is missing or invalid; apply "
            "remediation again before validation."
        ) from exc


def _verify_file_checksums(
    source_root: Path,
    working_root: Path,
    expected_records: list[FileChecksumRecord],
) -> list[FileChecksumVerification]:
    expected_by_path = {record.relative_path: record for record in expected_records}
    source_checksums = _inventory_checksums(source_root)
    output_checksums = _inventory_checksums(working_root)
    relative_paths = sorted(
        set(expected_by_path) | set(source_checksums) | set(output_checksums)
    )

    verifications: list[FileChecksumVerification] = []
    for relative_path in relative_paths:
        expected = expected_by_path.get(relative_path)
        actual_source = source_checksums.get(relative_path)
        actual_output = output_checksums.get(relative_path)
        expected_source = (
            expected.source_checksum_sha256 if expected is not None else None
        )
        expected_output = (
            expected.output_checksum_sha256 if expected is not None else None
        )
        verifications.append(
            FileChecksumVerification(
                relative_path=relative_path,
                expected_source_checksum_sha256=expected_source,
                actual_source_checksum_sha256=actual_source,
                source_checksum_verified=(
                    expected_source is not None and expected_source == actual_source
                ),
                expected_output_checksum_sha256=expected_output,
                actual_output_checksum_sha256=actual_output,
                output_checksum_verified=(
                    expected_output is not None and expected_output == actual_output
                ),
            )
        )
    return verifications


def _inventory_checksums(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): calculate_file_checksum(path)
        for path in directory.rglob("*")
        if path.is_file()
    }


def _finding_key(
    finding: InspectionFinding | FindingReference,
) -> tuple[str, str, str | None]:
    return finding.type.value, finding.file, finding.affected_column
