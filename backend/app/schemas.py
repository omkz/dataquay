from enum import StrEnum

from pydantic import BaseModel, Field


class CsvProfile(BaseModel):
    file_name: str
    row_count: int
    column_count: int
    column_names: list[str]
    data_types: dict[str, str]
    missing_value_counts: dict[str, int]
    duplicate_row_count: int


class DatasetSummary(BaseModel):
    dataset_name: str
    total_file_count: int
    csv_file_count: int
    total_size_bytes: int


class InspectedFile(BaseModel):
    file_name: str
    relative_path: str
    extension: str
    size_bytes: int
    csv_profile: CsvProfile | None = None


class FindingType(StrEnum):
    MISSING_VALUES = "missing_values"
    DUPLICATE_ROWS = "duplicate_rows"
    DUPLICATE_IDENTIFIER_VALUES = "duplicate_identifier_values"
    MISSING_REFERENCE = "missing_reference"
    INCONSISTENT_DATE_FORMATS = "inconsistent_date_formats"
    SUSPICIOUS_NUMERIC_VALUES = "suspicious_numeric_values"
    PROBABLE_PERSONAL_DATA = "probable_personal_data"


class FindingSeverity(StrEnum):
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InspectionFinding(BaseModel):
    type: FindingType
    severity: FindingSeverity
    file: str
    affected_column: str | None
    evidence: dict[str, int | str | list[str]]
    message: str


class ReadinessStatus(StrEnum):
    NOT_READY = "not_ready"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"


class ReadinessSummary(BaseModel):
    total_finding_count: int
    finding_counts_by_severity: dict[str, int]
    finding_counts_by_type: dict[str, int]
    blocker_count: int
    human_review_required: bool
    status: ReadinessStatus


class DatasetInspection(BaseModel):
    summary: DatasetSummary
    readiness: ReadinessSummary
    files: list[InspectedFile]
    findings: list[InspectionFinding]


class FindingReference(BaseModel):
    type: FindingType
    file: str
    affected_column: str | None


class RemediationRecommendation(BaseModel):
    related_finding: FindingReference
    short_title: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1)
    proposed_action: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    human_approval_required: bool


class RecommendationResponse(BaseModel):
    recommendations: list[RemediationRecommendation]


class RemediationOperation(StrEnum):
    REVIEW_MISSING_VALUES = "review_missing_values"
    REMOVE_EXACT_DUPLICATE_ROWS = "remove_exact_duplicate_rows"
    RESOLVE_DUPLICATE_IDENTIFIERS = "resolve_duplicate_identifiers"
    RECONCILE_MISSING_REFERENCES = "reconcile_missing_references"
    NORMALIZE_RECOGNIZED_DATE_FORMATS = "normalize_recognized_date_formats"
    REVIEW_SUSPICIOUS_NUMERIC_VALUES = "review_suspicious_numeric_values"
    REVIEW_PROBABLE_PERSONAL_DATA = "review_probable_personal_data"


class RemediationPreviewRequest(BaseModel):
    approved_recommendations: list[RemediationRecommendation]


class RemediationAction(BaseModel):
    related_finding: FindingReference
    target_file: str
    target_column: str | None
    proposed_operation: RemediationOperation
    can_apply_automatically: bool
    manual_review_reason: str | None
    expected_result: str


class RemediationPreviewResponse(BaseModel):
    actions: list[RemediationAction]
