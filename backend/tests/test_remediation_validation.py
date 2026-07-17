from pathlib import Path
import shutil

import pytest

from app.schemas import FindingType, RemediationRecommendation
from app.services.remediation_apply import apply_approved_remediation_actions
from app.services.remediation_validation import (
    ValidationUnavailableError,
    validate_remediated_dataset,
)

SAMPLE_DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "sample-data" / "soil-study"
)


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


def test_validation_compares_findings_checksums_and_updated_readiness(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    working_copy = tmp_path / "working-copy"
    shutil.copytree(SAMPLE_DATASET_PATH, source)
    apply_approved_remediation_actions(
        _safe_recommendations(),
        source,
        working_copy,
    )

    result = validate_remediated_dataset(source, working_copy)

    resolved_keys = {
        (finding.type.value, finding.file, finding.affected_column)
        for finding in result.resolved_findings
    }
    assert resolved_keys == {
        ("duplicate_rows", "observations.csv", None),
        (
            "duplicate_identifier_values",
            "observations.csv",
            "observation_id",
        ),
        (
            "inconsistent_date_formats",
            "participants.csv",
            "joined_at",
        ),
        (
            "inconsistent_date_formats",
            "observations.csv",
            "recorded_at",
        ),
    }
    assert len(result.remaining_findings) == 8
    missing_reference = next(
        finding
        for finding in result.remaining_findings
        if finding.type == FindingType.MISSING_REFERENCE
    )
    assert missing_reference.evidence["reference_count"] == 1

    assert len(result.checksum_verifications) == 3
    assert all(
        verification.source_checksum_verified
        for verification in result.checksum_verifications
    )
    assert all(
        verification.output_checksum_verified
        for verification in result.checksum_verifications
    )
    assert result.source_checksums_verified is True
    assert result.output_checksums_verified is True
    assert result.original_files_unchanged is True
    assert result.readiness.model_dump(mode="json") == {
        "total_finding_count": 8,
        "finding_counts_by_severity": {"high": 2, "medium": 6},
        "finding_counts_by_type": {
            "duplicate_identifier_values": 1,
            "missing_reference": 1,
            "missing_values": 2,
            "probable_personal_data": 2,
            "suspicious_numeric_values": 2,
        },
        "blocker_count": 2,
        "human_review_required": True,
        "status": "not_ready",
    }


def test_validation_detects_source_and_working_copy_checksum_changes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    working_copy = tmp_path / "working-copy"
    shutil.copytree(SAMPLE_DATASET_PATH, source)
    apply_approved_remediation_actions(
        _safe_recommendations(),
        source,
        working_copy,
    )
    (source / "README.md").write_text("changed source\n", encoding="utf-8")
    (working_copy / "README.md").write_text(
        "changed working copy\n",
        encoding="utf-8",
    )

    result = validate_remediated_dataset(source, working_copy)

    readme_verification = next(
        verification
        for verification in result.checksum_verifications
        if verification.relative_path == "README.md"
    )
    assert readme_verification.source_checksum_verified is False
    assert readme_verification.output_checksum_verified is False
    assert result.source_checksums_verified is False
    assert result.output_checksums_verified is False
    assert result.original_files_unchanged is False


def test_validation_requires_an_applied_working_copy(tmp_path: Path) -> None:
    with pytest.raises(
        ValidationUnavailableError,
        match="apply remediation first",
    ):
        validate_remediated_dataset(
            SAMPLE_DATASET_PATH,
            tmp_path / "missing-working-copy",
        )
