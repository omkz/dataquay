from io import BytesIO
import json
from pathlib import Path
import shutil
from zipfile import ZipFile

import polars as pl
import pytest

from app.schemas import FindingType, RemediationRecommendation
from app.services.package_generator import (
    PackageGenerationError,
    generate_dataset_package,
    get_package_zip_path,
)
from app.services.remediation_apply import (
    apply_approved_remediation_actions,
    calculate_file_checksum,
)

SAMPLE_DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "sample-data" / "soil-study"
)
EXPECTED_PACKAGE_FILES = {
    "README.md",
    "checksums.sha256",
    "data-dictionary.csv",
    "data/README.md",
    "data/observations.csv",
    "data/participants.csv",
    "file-manifest.json",
    "metadata.json",
    "provenance.json",
    "validation-report.json",
}


def _recommendation_for(
    finding_type: FindingType,
    file: str,
    column: str | None,
) -> RemediationRecommendation:
    return RemediationRecommendation.model_validate(
        {
            "related_finding": {
                "type": finding_type,
                "file": file,
                "affected_column": column,
            },
            "short_title": "Approved safe recommendation",
            "rationale": "The deterministic finding can be remediated safely.",
            "proposed_action": "Apply the deterministic operation.",
            "confidence": 0.98,
            "human_approval_required": True,
        }
    )


def _safe_recommendations() -> list[RemediationRecommendation]:
    return [
        _recommendation_for(
            FindingType.DUPLICATE_ROWS,
            "observations.csv",
            None,
        ),
        _recommendation_for(
            FindingType.INCONSISTENT_DATE_FORMATS,
            "participants.csv",
            "joined_at",
        ),
        _recommendation_for(
            FindingType.INCONSISTENT_DATE_FORMATS,
            "observations.csv",
            "recorded_at",
        ),
    ]


def _directory_contents(directory: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(directory): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_generate_package_contains_expected_artifacts_and_preserves_inputs(
    tmp_path: Path,
) -> None:
    source = tmp_path / "input" / "soil-study"
    working_copy = tmp_path / "working-copy"
    package_directory = tmp_path / "packages" / "soil-study"
    shutil.copytree(SAMPLE_DATASET_PATH, source)
    apply_approved_remediation_actions(
        _safe_recommendations(),
        source,
        working_copy,
    )
    source_before = _directory_contents(source)
    working_before = _directory_contents(working_copy)

    result = generate_dataset_package(
        source,
        working_copy,
        package_directory,
    )

    assert result.dataset_name == "soil-study"
    assert result.zip_file_name == "soil-study.zip"
    assert result.download_url == "/api/package/sample-dataset/download"
    assert result.readiness.total_finding_count == 8
    assert {entry.relative_path for entry in result.files} == EXPECTED_PACKAGE_FILES
    zip_path = get_package_zip_path(package_directory)
    assert result.zip_checksum_sha256 == calculate_file_checksum(zip_path)
    assert result.zip_size_bytes == zip_path.stat().st_size

    with ZipFile(BytesIO(zip_path.read_bytes())) as archive:
        assert set(archive.namelist()) == EXPECTED_PACKAGE_FILES

    metadata = json.loads((package_directory / "metadata.json").read_text())
    assert metadata["dataset_name"] == "soil-study"
    assert metadata["resolved_finding_count"] == 4
    assert metadata["remaining_finding_count"] == 8

    validation_report = json.loads(
        (package_directory / "validation-report.json").read_text()
    )
    assert validation_report["original_files_unchanged"] is True
    assert len(validation_report["resolved_findings"]) == 4
    assert len(validation_report["remaining_findings"]) == 8

    provenance = json.loads(
        (package_directory / "provenance.json").read_text()
    )
    assert len(provenance["applied_actions"]) == 3
    assert provenance["validation"] == {
        "original_files_unchanged": True,
        "output_checksums_verified": True,
        "source_checksums_verified": True,
    }

    file_manifest = json.loads(
        (package_directory / "file-manifest.json").read_text()
    )
    assert len(file_manifest["files"]) == 8
    manifest_paths = {entry["relative_path"] for entry in file_manifest["files"]}
    assert "data/observations.csv" in manifest_paths
    assert "validation-report.json" in manifest_paths

    checksum_lines = (package_directory / "checksums.sha256").read_text().splitlines()
    checksums = {
        relative_path: checksum
        for checksum, relative_path in (line.split("  ", maxsplit=1) for line in checksum_lines)
    }
    assert set(checksums) == EXPECTED_PACKAGE_FILES - {"checksums.sha256"}
    assert all(
        checksum == calculate_file_checksum(package_directory / relative_path)
        for relative_path, checksum in checksums.items()
    )

    observations = pl.read_csv(package_directory / "data" / "observations.csv")
    assert observations.height == 3
    assert set(observations["recorded_at"].to_list()) == {
        "2026-02-01",
        "2026-02-02",
    }
    assert "participants.csv,joined_at,String,0" in (
        package_directory / "data-dictionary.csv"
    ).read_text()

    first_zip = zip_path.read_bytes()
    repeated_result = generate_dataset_package(
        source,
        working_copy,
        package_directory,
    )
    assert zip_path.read_bytes() == first_zip
    assert repeated_result.zip_checksum_sha256 == result.zip_checksum_sha256
    assert _directory_contents(source) == source_before
    assert _directory_contents(working_copy) == working_before


def test_generate_package_fails_when_working_copy_is_missing(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        PackageGenerationError,
        match="working copy does not exist",
    ):
        generate_dataset_package(
            SAMPLE_DATASET_PATH,
            tmp_path / "missing-working-copy",
            tmp_path / "package",
        )


def test_generate_package_fails_when_checksum_validation_fails(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    working_copy = tmp_path / "working-copy"
    package_directory = tmp_path / "package"
    shutil.copytree(SAMPLE_DATASET_PATH, source)
    apply_approved_remediation_actions(
        _safe_recommendations(),
        source,
        working_copy,
    )
    (working_copy / "README.md").write_text(
        "tampered after remediation\n",
        encoding="utf-8",
    )

    with pytest.raises(
        PackageGenerationError,
        match="checksum validation failed",
    ):
        generate_dataset_package(source, working_copy, package_directory)

    assert not package_directory.exists()
    assert not get_package_zip_path(package_directory).exists()
