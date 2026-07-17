import csv
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from app.schemas import (
    DatasetInspection,
    DatasetValidationResult,
    PackageFileEntry,
    PackageGenerationResult,
    RemediationChecksumManifest,
)
from app.services.dataset_inspector import inspect_dataset
from app.services.remediation_apply import calculate_file_checksum
from app.services.remediation_validation import (
    ValidationUnavailableError,
    load_checksum_manifest,
    validate_remediated_dataset,
)

PACKAGE_DOWNLOAD_URL = "/api/package/sample-dataset/download"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class PackageGenerationError(RuntimeError):
    """Raised when a trustworthy final package cannot be generated."""


def generate_dataset_package(
    source_directory: str | Path,
    working_copy_directory: str | Path,
    package_directory: str | Path,
    *,
    dataset_name: str | None = None,
    download_url: str = PACKAGE_DOWNLOAD_URL,
) -> PackageGenerationResult:
    """Build a deterministic package without modifying source or working files."""
    source_root = Path(source_directory).resolve(strict=True)
    working_root = Path(working_copy_directory).resolve()
    package_root = Path(package_directory).resolve()
    _validate_package_path(source_root, working_root, package_root)

    try:
        validation = validate_remediated_dataset(source_root, working_root)
    except ValidationUnavailableError as exc:
        raise PackageGenerationError(str(exc)) from exc

    if not (
        validation.source_checksums_verified
        and validation.output_checksums_verified
        and validation.original_files_unchanged
    ):
        raise PackageGenerationError(
            "Package generation stopped because source or output checksum "
            "validation failed. Apply remediation again before packaging."
        )

    source_inspection = inspect_dataset(source_root)
    resolved_dataset_name = dataset_name or source_inspection.summary.dataset_name
    inspection = inspect_dataset(working_root)
    inspection = inspection.model_copy(
        update={
            "summary": inspection.summary.model_copy(
                update={
                    "dataset_name": resolved_dataset_name,
                }
            )
        }
    )
    remediation_manifest = load_checksum_manifest(working_root)
    package_root.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(
        dir=package_root.parent,
        prefix=f".{package_root.name}-package-",
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        staged_package = temporary_root / package_root.name
        staged_package.mkdir()
        _build_package_contents(
            staged_package,
            working_root,
            inspection,
            validation,
            remediation_manifest,
        )
        staged_zip = temporary_root / f"{package_root.name}.zip"
        _write_deterministic_zip(staged_package, staged_zip)

        if package_root.exists():
            shutil.rmtree(package_root)
        shutil.move(staged_package, package_root)
        zip_path = package_root.with_suffix(".zip")
        staged_zip.replace(zip_path)

    return PackageGenerationResult(
        dataset_name=inspection.summary.dataset_name,
        zip_file_name=zip_path.name,
        zip_size_bytes=zip_path.stat().st_size,
        zip_checksum_sha256=calculate_file_checksum(zip_path),
        download_url=download_url,
        files=_package_file_entries(package_root),
        readiness=validation.readiness,
    )


def get_package_zip_path(package_directory: str | Path) -> Path:
    return Path(package_directory).resolve().with_suffix(".zip")


def _build_package_contents(
    package_root: Path,
    working_root: Path,
    inspection: DatasetInspection,
    validation: DatasetValidationResult,
    remediation_manifest: RemediationChecksumManifest,
) -> None:
    data_directory = package_root / "data"
    shutil.copytree(working_root, data_directory)

    _write_text(package_root / "README.md", _build_readme(inspection, validation))
    _write_data_dictionary(package_root / "data-dictionary.csv", inspection)
    _write_json(
        package_root / "metadata.json",
        {
            "dataset_name": inspection.summary.dataset_name,
            "package_version": "1.0",
            "summary": inspection.summary.model_dump(mode="json"),
            "readiness": validation.readiness.model_dump(mode="json"),
            "resolved_finding_count": len(validation.resolved_findings),
            "remaining_finding_count": len(validation.remaining_findings),
        },
    )
    _write_json(
        package_root / "validation-report.json",
        validation.model_dump(mode="json"),
    )
    _write_json(
        package_root / "provenance.json",
        {
            "source_dataset": inspection.summary.dataset_name,
            "statement": (
                "DataQuay generated this package from a validated working copy; "
                "the original and working datasets were not modified during packaging."
            ),
            "applied_actions": [
                result.model_dump(mode="json")
                for result in remediation_manifest.applied_actions
            ],
            "skipped_actions": [
                result.model_dump(mode="json")
                for result in remediation_manifest.skipped_actions
            ],
            "failed_actions": [
                result.model_dump(mode="json")
                for result in remediation_manifest.failed_actions
            ],
            "source_and_output_checksums": [
                record.model_dump(mode="json")
                for record in remediation_manifest.files
            ],
            "validation": {
                "original_files_unchanged": validation.original_files_unchanged,
                "source_checksums_verified": validation.source_checksums_verified,
                "output_checksums_verified": validation.output_checksums_verified,
            },
        },
    )

    manifest_entries = [
        entry.model_dump(mode="json")
        for entry in _package_file_entries(package_root)
    ]
    _write_json(
        package_root / "file-manifest.json",
        {"files": manifest_entries},
    )
    checksum_lines = [
        f"{entry.checksum_sha256}  {entry.relative_path}"
        for entry in _package_file_entries(package_root)
    ]
    _write_text(
        package_root / "checksums.sha256",
        "\n".join(checksum_lines) + "\n",
    )


def _build_readme(
    inspection: DatasetInspection,
    validation: DatasetValidationResult,
) -> str:
    file_lines = "\n".join(
        f"- `{file.relative_path}` ({file.size_bytes} bytes)"
        for file in inspection.files
    )
    return (
        f"# {inspection.summary.dataset_name}\n\n"
        "This package was generated deterministically by DataQuay from the "
        "validated remediated working copy.\n\n"
        "## Validation summary\n\n"
        f"- Readiness: `{validation.readiness.status.value}`\n"
        f"- Resolved findings: {len(validation.resolved_findings)}\n"
        f"- Remaining findings: {len(validation.remaining_findings)}\n"
        f"- Original files unchanged: {str(validation.original_files_unchanged).lower()}\n\n"
        "## Data files\n\n"
        f"{file_lines}\n"
    )


def _write_data_dictionary(path: Path, inspection: DatasetInspection) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            ["file", "column", "data_type", "missing_value_count"]
        )
        for file in inspection.files:
            profile = file.csv_profile
            if profile is None:
                continue
            for column in profile.column_names:
                writer.writerow(
                    [
                        file.relative_path,
                        column,
                        profile.data_types[column],
                        profile.missing_value_counts[column],
                    ]
                )


def _write_json(path: Path, value: object) -> None:
    _write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def _package_file_entries(package_root: Path) -> list[PackageFileEntry]:
    return [
        PackageFileEntry(
            relative_path=path.relative_to(package_root).as_posix(),
            size_bytes=path.stat().st_size,
            checksum_sha256=calculate_file_checksum(path),
        )
        for path in sorted(package_root.rglob("*"))
        if path.is_file()
    ]


def _write_deterministic_zip(package_root: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w") as archive:
        for file_path in sorted(package_root.rglob("*")):
            if not file_path.is_file():
                continue
            archive_path = file_path.relative_to(package_root).as_posix()
            zip_info = ZipInfo(archive_path, date_time=ZIP_TIMESTAMP)
            zip_info.compress_type = ZIP_DEFLATED
            zip_info.external_attr = 0o100644 << 16
            archive.writestr(zip_info, file_path.read_bytes())


def _validate_package_path(
    source_root: Path,
    working_root: Path,
    package_root: Path,
) -> None:
    filesystem_root = Path(package_root.anchor)
    protected_roots = (source_root, working_root)
    overlaps_protected_path = any(
        package_root == protected
        or package_root in protected.parents
        or protected in package_root.parents
        for protected in protected_roots
    )
    if package_root == filesystem_root or overlaps_protected_path:
        raise PackageGenerationError(
            "The package directory must be separate from source and working data."
        )
