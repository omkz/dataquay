from dataclasses import dataclass

from app.schemas import (
    FindingReference,
    FindingType,
    InspectionFinding,
    RemediationAction,
    RemediationOperation,
    RemediationPreviewResponse,
    RemediationRecommendation,
)


class UnknownFindingReferenceError(ValueError):
    """Raised when a recommendation does not reference a current finding."""


@dataclass(frozen=True)
class RemediationRule:
    operation: RemediationOperation
    can_apply_automatically: bool
    manual_review_reason: str | None
    expected_result: str


REMEDIATION_RULES = {
    FindingType.MISSING_VALUES: RemediationRule(
        operation=RemediationOperation.REVIEW_MISSING_VALUES,
        can_apply_automatically=False,
        manual_review_reason=(
            "The correct treatment depends on the research context and cannot be "
            "inferred from a missing value alone."
        ),
        expected_result=(
            "Missing values have a steward-approved treatment or are retained with "
            "clear documentation."
        ),
    ),
    FindingType.DUPLICATE_ROWS: RemediationRule(
        operation=RemediationOperation.REMOVE_EXACT_DUPLICATE_ROWS,
        can_apply_automatically=True,
        manual_review_reason=None,
        expected_result=(
            "Only one copy of each exact duplicate row remains in the target file."
        ),
    ),
    FindingType.DUPLICATE_IDENTIFIER_VALUES: RemediationRule(
        operation=RemediationOperation.RESOLVE_DUPLICATE_IDENTIFIERS,
        can_apply_automatically=False,
        manual_review_reason=(
            "Duplicate identifiers may represent repeated measurements, data-entry "
            "errors, or distinct records and require domain interpretation."
        ),
        expected_result=(
            "Identifier values are unique where required, with any intentional reuse "
            "documented."
        ),
    ),
    FindingType.MISSING_REFERENCE: RemediationRule(
        operation=RemediationOperation.RECONCILE_MISSING_REFERENCES,
        can_apply_automatically=False,
        manual_review_reason=(
            "The service cannot infer whether the reference, the parent record, or "
            "the relationship definition should change."
        ),
        expected_result=(
            "Each reference resolves to an existing identifier or has a documented "
            "exception."
        ),
    ),
    FindingType.INCONSISTENT_DATE_FORMATS: RemediationRule(
        operation=RemediationOperation.NORMALIZE_RECOGNIZED_DATE_FORMATS,
        can_apply_automatically=True,
        manual_review_reason=None,
        expected_result=(
            "Recognized dates use ISO 8601 YYYY-MM-DD format without changing their "
            "calendar dates."
        ),
    ),
    FindingType.SUSPICIOUS_NUMERIC_VALUES: RemediationRule(
        operation=RemediationOperation.REVIEW_SUSPICIOUS_NUMERIC_VALUES,
        can_apply_automatically=False,
        manual_review_reason=(
            "A suspicious number may be a valid observation, a sentinel, or an error; "
            "its meaning requires domain context."
        ),
        expected_result=(
            "Suspicious values are retained, replaced, or marked missing according to "
            "a steward-approved interpretation."
        ),
    ),
    FindingType.PROBABLE_PERSONAL_DATA: RemediationRule(
        operation=RemediationOperation.REVIEW_PROBABLE_PERSONAL_DATA,
        can_apply_automatically=False,
        manual_review_reason=(
            "Pattern and column-name detection indicates probable personal data but "
            "does not establish context, consent, policy, or legal classification."
        ),
        expected_result=(
            "The probable personal-data field has an approved privacy treatment or a "
            "documented decision to retain it."
        ),
    ),
}


def preview_remediation_actions(
    approved_recommendations: list[RemediationRecommendation],
    findings: list[InspectionFinding],
) -> RemediationPreviewResponse:
    """Translate approved recommendations into deterministic, read-only actions."""
    finding_index = {_finding_key(finding): finding for finding in findings}
    actions: list[RemediationAction] = []

    for recommendation in approved_recommendations:
        reference = recommendation.related_finding
        finding = finding_index.get(_finding_key(reference))
        if finding is None:
            raise UnknownFindingReferenceError(
                "Approved recommendation references a finding that is not present "
                f"in the current inspection: {reference.type.value} in "
                f"'{reference.file}' ({reference.affected_column or 'file level'})."
            )

        rule = REMEDIATION_RULES[finding.type]
        actions.append(
            RemediationAction(
                related_finding=FindingReference(
                    type=finding.type,
                    file=finding.file,
                    affected_column=finding.affected_column,
                ),
                target_file=finding.file,
                target_column=finding.affected_column,
                proposed_operation=rule.operation,
                can_apply_automatically=rule.can_apply_automatically,
                manual_review_reason=rule.manual_review_reason,
                expected_result=rule.expected_result,
            )
        )

    return RemediationPreviewResponse(actions=actions)


def _finding_key(
    finding: InspectionFinding | FindingReference,
) -> tuple[FindingType, str, str | None]:
    return finding.type, finding.file, finding.affected_column
