from collections import Counter
from datetime import datetime
from pathlib import Path

import polars as pl

from app.schemas import (
    FindingSeverity,
    FindingType,
    InspectedFile,
    InspectionFinding,
)
from app.services.privacy_detector import detect_probable_personal_data

DATE_FORMATS = (
    ("YYYY-MM-DD", "%Y-%m-%d"),
    ("DD/MM/YYYY", "%d/%m/%Y"),
    ("Month D YYYY", "%B %d %Y"),
)
SUSPICIOUS_NUMERIC_SENTINELS = {-9999.0, -999.0, -99.0, -9.0, 999.0, 9999.0}


def detect_inspection_findings(
    directory: Path, files: list[InspectedFile]
) -> list[InspectionFinding]:
    """Detect deterministic data-quality and cross-file reference findings."""
    csv_files = [file for file in files if file.csv_profile is not None]
    data_frames = {
        file.relative_path: pl.read_csv(directory / file.relative_path)
        for file in csv_files
    }
    findings: list[InspectionFinding] = []
    primary_identifiers: dict[str, tuple[InspectedFile, set[str]]] = {}

    for file in csv_files:
        profile = file.csv_profile
        if profile is None:
            continue

        for column, missing_count in profile.missing_value_counts.items():
            if missing_count:
                findings.append(
                    InspectionFinding(
                        type=FindingType.MISSING_VALUES,
                        severity=FindingSeverity.MEDIUM,
                        file=file.relative_path,
                        affected_column=column,
                        evidence={"missing_count": missing_count},
                        message=(
                            f"Column '{column}' contains {missing_count} missing "
                            f"value{'s' if missing_count != 1 else ''}."
                        ),
                    )
                )

        if profile.duplicate_row_count:
            findings.append(
                InspectionFinding(
                    type=FindingType.DUPLICATE_ROWS,
                    severity=FindingSeverity.MEDIUM,
                    file=file.relative_path,
                    affected_column=None,
                    evidence={"duplicate_row_count": profile.duplicate_row_count},
                    message=(
                        f"File contains {profile.duplicate_row_count} duplicate "
                        f"row{'s' if profile.duplicate_row_count != 1 else ''}."
                    ),
                )
            )

        findings.extend(
            _detect_inconsistent_date_formats(file, data_frames[file.relative_path])
        )
        findings.extend(
            _detect_suspicious_numeric_values(file, data_frames[file.relative_path])
        )
        findings.extend(
            detect_probable_personal_data(file, data_frames[file.relative_path])
        )

        identifier_column = _primary_identifier_column(profile.column_names)
        if identifier_column is None:
            continue

        identifier_values = [
            str(value)
            for value in data_frames[file.relative_path][identifier_column].to_list()
            if value is not None
        ]
        value_counts = Counter(identifier_values)
        duplicate_values = sorted(
            value for value, count in value_counts.items() if count > 1
        )
        if duplicate_values:
            duplicate_count = sum(value_counts[value] - 1 for value in duplicate_values)
            findings.append(
                InspectionFinding(
                    type=FindingType.DUPLICATE_IDENTIFIER_VALUES,
                    severity=FindingSeverity.HIGH,
                    file=file.relative_path,
                    affected_column=identifier_column,
                    evidence={
                        "duplicate_count": duplicate_count,
                        "duplicate_values": duplicate_values,
                    },
                    message=(
                        f"Identifier column '{identifier_column}' contains "
                        f"duplicate values: {', '.join(duplicate_values)}."
                    ),
                )
            )

        primary_identifiers[identifier_column] = (file, set(identifier_values))

    findings.extend(
        _detect_missing_references(csv_files, data_frames, primary_identifiers)
    )
    return findings


def _detect_inconsistent_date_formats(
    file: InspectedFile, data: pl.DataFrame
) -> list[InspectionFinding]:
    findings: list[InspectionFinding] = []

    for column in data.columns:
        if data[column].dtype != pl.String or not _is_date_column(column):
            continue

        values_by_format: dict[str, list[str]] = {}
        values = data[column].drop_nulls().unique(maintain_order=True).to_list()
        for value in values:
            value_text = str(value)
            date_format = _classify_date_format(value_text)
            if date_format is not None:
                values_by_format.setdefault(date_format, []).append(value_text)

        if len(values_by_format) < 2:
            continue

        detected_formats = [
            label for label, _ in DATE_FORMATS if label in values_by_format
        ]
        triggering_values = [
            f"{value} ({label})"
            for label in detected_formats
            for value in values_by_format[label]
        ]
        findings.append(
            InspectionFinding(
                type=FindingType.INCONSISTENT_DATE_FORMATS,
                severity=FindingSeverity.MEDIUM,
                file=file.relative_path,
                affected_column=column,
                evidence={
                    "detected_formats": detected_formats,
                    "triggering_values": triggering_values,
                },
                message=(
                    f"Column '{column}' contains inconsistent date formats: "
                    f"{', '.join(detected_formats)}."
                ),
            )
        )

    return findings


def _detect_suspicious_numeric_values(
    file: InspectedFile, data: pl.DataFrame
) -> list[InspectionFinding]:
    findings: list[InspectionFinding] = []

    for column in data.columns:
        if not data[column].dtype.is_numeric():
            continue

        suspicious_values = [
            value
            for value in data[column].drop_nulls().to_list()
            if float(value) in SUSPICIOUS_NUMERIC_SENTINELS
        ]
        if not suspicious_values:
            continue

        formatted_values = sorted(
            {_format_numeric_value(value) for value in suspicious_values}
        )
        findings.append(
            InspectionFinding(
                type=FindingType.SUSPICIOUS_NUMERIC_VALUES,
                severity=FindingSeverity.MEDIUM,
                file=file.relative_path,
                affected_column=column,
                evidence={
                    "suspicious_values": formatted_values,
                    "occurrence_count": len(suspicious_values),
                    "reason": "matches a common placeholder or invalid sentinel value",
                },
                message=(
                    f"Column '{column}' contains suspicious numeric values: "
                    f"{', '.join(formatted_values)}."
                ),
            )
        )

    return findings


def _is_date_column(column: str) -> bool:
    normalized = column.lower()
    return normalized == "date" or normalized.endswith(("_date", "_at"))


def _classify_date_format(value: str) -> str | None:
    for label, date_format in DATE_FORMATS:
        try:
            datetime.strptime(value, date_format)
        except ValueError:
            continue
        return label
    return None


def _format_numeric_value(value: int | float) -> str:
    numeric_value = float(value)
    if numeric_value.is_integer():
        return str(int(numeric_value))
    return str(numeric_value)


def _primary_identifier_column(column_names: list[str]) -> str | None:
    if not column_names:
        return None

    first_column = column_names[0]
    if first_column == "id" or first_column.endswith("_id"):
        return first_column
    return None


def _detect_missing_references(
    csv_files: list[InspectedFile],
    data_frames: dict[str, pl.DataFrame],
    primary_identifiers: dict[str, tuple[InspectedFile, set[str]]],
) -> list[InspectionFinding]:
    findings: list[InspectionFinding] = []

    for file in csv_files:
        data = data_frames[file.relative_path]
        primary_column = _primary_identifier_column(data.columns)

        for column in data.columns:
            reference = primary_identifiers.get(column)
            if reference is None or column == primary_column:
                continue

            referenced_file, valid_values = reference
            if referenced_file.relative_path == file.relative_path:
                continue

            values = [
                str(value) for value in data[column].to_list() if value is not None
            ]
            missing_values = sorted(set(values) - valid_values)
            if not missing_values:
                continue

            reference_count = sum(value in missing_values for value in values)
            findings.append(
                InspectionFinding(
                    type=FindingType.MISSING_REFERENCE,
                    severity=FindingSeverity.HIGH,
                    file=file.relative_path,
                    affected_column=column,
                    evidence={
                        "referenced_file": referenced_file.relative_path,
                        "missing_values": missing_values,
                        "reference_count": reference_count,
                    },
                    message=(
                        f"Column '{column}' contains values not found in "
                        f"'{referenced_file.relative_path}': "
                        f"{', '.join(missing_values)}."
                    ),
                )
            )

    return findings
