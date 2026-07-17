from enum import StrEnum

from pydantic import BaseModel


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
