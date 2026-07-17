import pytest

from app.schemas import (
    FindingSeverity,
    FindingType,
    InspectionFinding,
    ReadinessStatus,
)
from app.services.readiness import calculate_readiness


def _finding(
    finding_type: FindingType, severity: FindingSeverity
) -> InspectionFinding:
    return InspectionFinding(
        type=finding_type,
        severity=severity,
        file="data.csv",
        affected_column="value",
        evidence={},
        message="Test finding.",
    )


@pytest.mark.parametrize(
    "severity", [FindingSeverity.HIGH, FindingSeverity.CRITICAL]
)
def test_readiness_is_not_ready_for_blocking_findings(
    severity: FindingSeverity,
) -> None:
    readiness = calculate_readiness(
        [_finding(FindingType.MISSING_REFERENCE, severity)]
    )

    assert readiness.status == ReadinessStatus.NOT_READY
    assert readiness.total_finding_count == 1
    assert readiness.finding_counts_by_severity == {severity.value: 1}
    assert readiness.finding_counts_by_type == {"missing_reference": 1}
    assert readiness.blocker_count == 1
    assert readiness.human_review_required is True


def test_readiness_needs_review_for_probable_personal_data_without_blockers(
) -> None:
    readiness = calculate_readiness(
        [
            _finding(
                FindingType.PROBABLE_PERSONAL_DATA,
                FindingSeverity.MEDIUM,
            )
        ]
    )

    assert readiness.status == ReadinessStatus.NEEDS_REVIEW
    assert readiness.blocker_count == 0
    assert readiness.human_review_required is True


def test_readiness_is_ready_without_blockers_or_probable_personal_data() -> None:
    readiness = calculate_readiness(
        [_finding(FindingType.MISSING_VALUES, FindingSeverity.MEDIUM)]
    )

    assert readiness.status == ReadinessStatus.READY
    assert readiness.total_finding_count == 1
    assert readiness.finding_counts_by_severity == {"medium": 1}
    assert readiness.finding_counts_by_type == {"missing_values": 1}
    assert readiness.blocker_count == 0
    assert readiness.human_review_required is False
