from collections import Counter

from app.schemas import (
    FindingSeverity,
    FindingType,
    InspectionFinding,
    ReadinessStatus,
    ReadinessSummary,
)

BLOCKER_SEVERITIES = {FindingSeverity.HIGH, FindingSeverity.CRITICAL}


def calculate_readiness(findings: list[InspectionFinding]) -> ReadinessSummary:
    """Aggregate findings and calculate deterministic dataset readiness."""
    severity_counts = Counter(finding.severity.value for finding in findings)
    type_counts = Counter(finding.type.value for finding in findings)
    blocker_count = sum(
        finding.severity in BLOCKER_SEVERITIES for finding in findings
    )
    has_probable_personal_data = any(
        finding.type == FindingType.PROBABLE_PERSONAL_DATA for finding in findings
    )

    if blocker_count:
        status = ReadinessStatus.NOT_READY
    elif has_probable_personal_data:
        status = ReadinessStatus.NEEDS_REVIEW
    else:
        status = ReadinessStatus.READY

    return ReadinessSummary(
        total_finding_count=len(findings),
        finding_counts_by_severity=dict(sorted(severity_counts.items())),
        finding_counts_by_type=dict(sorted(type_counts.items())),
        blocker_count=blocker_count,
        human_review_required=status != ReadinessStatus.READY,
        status=status,
    )
