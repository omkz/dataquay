from collections import Counter
from pathlib import Path

import polars as pl

from app.schemas import (
    FindingSeverity,
    FindingType,
    InspectedFile,
    InspectionFinding,
)


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
