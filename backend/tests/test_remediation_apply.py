from pathlib import Path

import polars as pl
import pytest

from app.schemas import FindingType, RemediationRecommendation
from app.services.remediation_apply import (
    InvalidWorkingCopyPathError,
    apply_approved_remediation_actions,
    calculate_file_checksum,
    get_checksum_manifest_path,
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
            "short_title": "Approved recommendation",
            "rationale": "The finding should be addressed.",
            "proposed_action": "Prepare the deterministic action.",
            "confidence": 0.95,
            "human_approval_required": True,
        }
    )


def _directory_contents(directory: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(directory): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_apply_uses_a_repeatable_working_copy_and_preserves_originals(
    tmp_path: Path,
) -> None:
    working_copy = tmp_path / "working-copy"
    original_contents = _directory_contents(SAMPLE_DATASET_PATH)
    recommendations = [
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
        _recommendation_for(
            FindingType.SUSPICIOUS_NUMERIC_VALUES,
            "observations.csv",
            "soil_moisture",
        ),
        _recommendation_for(
            FindingType.DUPLICATE_IDENTIFIER_VALUES,
            "participants.csv",
            "participant_id",
        ),
    ]

    first_result = apply_approved_remediation_actions(
        recommendations,
        SAMPLE_DATASET_PATH,
        working_copy,
    )

    assert len(first_result.applied_actions) == 3
    assert len(first_result.skipped_actions) == 2
    assert first_result.failed_actions == []
    assert [record.relative_path for record in first_result.file_checksums] == [
        "README.md",
        "observations.csv",
        "participants.csv",
    ]
    assert get_checksum_manifest_path(working_copy).is_file()
    assert all(
        result.action.can_apply_automatically
        for result in first_result.applied_actions
    )
    assert all(
        not result.action.can_apply_automatically
        for result in first_result.skipped_actions
    )
    assert all(
        "requires manual review" in result.message
        for result in first_result.skipped_actions
    )

    observations = pl.read_csv(working_copy / "observations.csv")
    assert observations.height == 3
    assert observations["recorded_at"].to_list() == [
        "2026-02-01",
        "2026-02-01",
        "2026-02-02",
    ]
    assert observations["soil_moisture"].to_list() == [42.5, -99.0, 38.1]

    participants = pl.read_csv(working_copy / "participants.csv")
    assert participants["joined_at"].to_list() == [
        "2026-01-15",
        "2026-01-15",
        "2026-01-15",
        "2026-01-16",
    ]
    assert participants["participant_id"].to_list() == [
        "P001",
        "P002",
        "P002",
        "P003",
    ]
    assert (working_copy / "README.md").read_bytes() == original_contents[
        Path("README.md")
    ]

    for result in [
        *first_result.applied_actions,
        *first_result.skipped_actions,
    ]:
        assert result.source_checksum_sha256 == calculate_file_checksum(
            SAMPLE_DATASET_PATH / result.action.target_file
        )
        assert result.output_checksum_sha256 is not None
        assert len(result.output_checksum_sha256) == 64

    for record in first_result.file_checksums:
        assert record.source_checksum_sha256 == calculate_file_checksum(
            SAMPLE_DATASET_PATH / record.relative_path
        )
        assert record.output_checksum_sha256 == calculate_file_checksum(
            working_copy / record.relative_path
        )

    first_working_contents = _directory_contents(working_copy)
    second_result = apply_approved_remediation_actions(
        recommendations,
        SAMPLE_DATASET_PATH,
        working_copy,
    )

    assert _directory_contents(working_copy) == first_working_contents
    assert second_result.model_dump() == first_result.model_dump()
    assert _directory_contents(SAMPLE_DATASET_PATH) == original_contents


def test_apply_reports_an_individual_safe_action_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    working_copy = tmp_path / "working-copy"
    recommendation = _recommendation_for(
        FindingType.DUPLICATE_ROWS,
        "observations.csv",
        None,
    )

    def fail_action(*args: object) -> None:
        raise RuntimeError("simulated transformation failure")

    monkeypatch.setattr(
        "app.services.remediation_apply._apply_automatic_action",
        fail_action,
    )

    result = apply_approved_remediation_actions(
        [recommendation],
        SAMPLE_DATASET_PATH,
        working_copy,
    )

    assert result.applied_actions == []
    assert result.skipped_actions == []
    assert len(result.failed_actions) == 1
    assert result.failed_actions[0].message == "Action failed with RuntimeError."
    assert result.failed_actions[0].source_checksum_sha256 == (
        result.failed_actions[0].output_checksum_sha256
    )


def test_apply_rejects_a_working_copy_that_overlaps_the_source() -> None:
    recommendation = _recommendation_for(
        FindingType.DUPLICATE_ROWS,
        "observations.csv",
        None,
    )

    with pytest.raises(
        InvalidWorkingCopyPathError,
        match="separate from the source dataset",
    ):
        apply_approved_remediation_actions(
            [recommendation],
            SAMPLE_DATASET_PATH,
            SAMPLE_DATASET_PATH,
        )
