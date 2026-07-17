from pathlib import Path

import pytest

from app.schemas import (
    FindingType,
    RemediationOperation,
    RemediationRecommendation,
)
from app.services.dataset_inspector import inspect_dataset
from app.services.remediation_preview import (
    UnknownFindingReferenceError,
    preview_remediation_actions,
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
            "proposed_action": "Untrusted free-form proposal text.",
            "confidence": 0.9,
            "human_approval_required": True,
        }
    )


@pytest.mark.parametrize(
    ("finding_type", "file", "column", "operation"),
    [
        (
            FindingType.DUPLICATE_ROWS,
            "observations.csv",
            None,
            RemediationOperation.REMOVE_EXACT_DUPLICATE_ROWS,
        ),
        (
            FindingType.INCONSISTENT_DATE_FORMATS,
            "participants.csv",
            "joined_at",
            RemediationOperation.NORMALIZE_RECOGNIZED_DATE_FORMATS,
        ),
    ],
)
def test_preview_marks_safe_deterministic_actions_as_automatically_applicable(
    finding_type: FindingType,
    file: str,
    column: str | None,
    operation: RemediationOperation,
) -> None:
    inspection = inspect_dataset(SAMPLE_DATASET_PATH)

    preview = preview_remediation_actions(
        [_recommendation_for(finding_type, file, column)],
        inspection.findings,
    )

    action = preview.actions[0]
    assert action.related_finding.type == finding_type
    assert action.target_file == file
    assert action.target_column == column
    assert action.proposed_operation == operation
    assert action.can_apply_automatically is True
    assert action.manual_review_reason is None
    assert action.expected_result


@pytest.mark.parametrize(
    ("finding_type", "file", "column", "operation"),
    [
        (
            FindingType.MISSING_VALUES,
            "participants.csv",
            "email",
            RemediationOperation.REVIEW_MISSING_VALUES,
        ),
        (
            FindingType.DUPLICATE_IDENTIFIER_VALUES,
            "participants.csv",
            "participant_id",
            RemediationOperation.RESOLVE_DUPLICATE_IDENTIFIERS,
        ),
        (
            FindingType.MISSING_REFERENCE,
            "observations.csv",
            "participant_id",
            RemediationOperation.RECONCILE_MISSING_REFERENCES,
        ),
        (
            FindingType.SUSPICIOUS_NUMERIC_VALUES,
            "observations.csv",
            "soil_moisture",
            RemediationOperation.REVIEW_SUSPICIOUS_NUMERIC_VALUES,
        ),
        (
            FindingType.PROBABLE_PERSONAL_DATA,
            "participants.csv",
            "email",
            RemediationOperation.REVIEW_PROBABLE_PERSONAL_DATA,
        ),
    ],
)
def test_preview_requires_manual_review_for_ambiguous_actions(
    finding_type: FindingType,
    file: str,
    column: str,
    operation: RemediationOperation,
) -> None:
    inspection = inspect_dataset(SAMPLE_DATASET_PATH)

    preview = preview_remediation_actions(
        [_recommendation_for(finding_type, file, column)],
        inspection.findings,
    )

    action = preview.actions[0]
    assert action.proposed_operation == operation
    assert action.can_apply_automatically is False
    assert action.manual_review_reason
    assert action.expected_result


def test_preview_rejects_recommendations_for_unknown_findings() -> None:
    inspection = inspect_dataset(SAMPLE_DATASET_PATH)
    recommendation = _recommendation_for(
        FindingType.DUPLICATE_ROWS,
        "not-in-the-dataset.csv",
        None,
    )

    with pytest.raises(
        UnknownFindingReferenceError,
        match="not present in the current inspection",
    ):
        preview_remediation_actions([recommendation], inspection.findings)


def test_preview_accepts_an_empty_approved_recommendation_list() -> None:
    inspection = inspect_dataset(SAMPLE_DATASET_PATH)

    preview = preview_remediation_actions([], inspection.findings)

    assert preview.actions == []
