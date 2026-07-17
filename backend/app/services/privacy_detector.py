import re

import polars as pl

from app.schemas import (
    FindingSeverity,
    FindingType,
    InspectedFile,
    InspectionFinding,
)

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_{|}~-]+"
    r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_{|}~-]+)*@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
PERSONAL_DATA_COLUMN_CATEGORIES = {
    "name": "person_name",
    "full_name": "person_name",
    "first_name": "person_name",
    "last_name": "person_name",
    "email": "email_address",
    "email_address": "email_address",
}
MAX_MASKED_EXAMPLES = 3


def detect_probable_personal_data(
    file: InspectedFile, data: pl.DataFrame
) -> list[InspectionFinding]:
    """Detect probable personal data without exposing complete source values."""
    findings: list[InspectionFinding] = []

    for column in data.columns:
        if data[column].dtype != pl.String:
            continue

        values = [
            str(value)
            for value in data[column].drop_nulls().to_list()
            if str(value).strip()
        ]
        categories: dict[str, set[str]] = {}

        column_category = PERSONAL_DATA_COLUMN_CATEGORIES.get(column.lower())
        if column_category is not None:
            categories.setdefault(column_category, set()).add("column_name")

        email_values = [value for value in values if EMAIL_PATTERN.fullmatch(value)]
        if email_values:
            categories.setdefault("email_address", set()).add("pattern_match")

        for category, detection_methods in categories.items():
            matched_values = (
                email_values
                if category == "email_address" and "pattern_match" in detection_methods
                else values
            )
            if not matched_values:
                continue

            masked_evidence = _unique_masked_examples(matched_values, category)
            methods = sorted(detection_methods)
            findings.append(
                InspectionFinding(
                    type=FindingType.PROBABLE_PERSONAL_DATA,
                    severity=FindingSeverity.MEDIUM,
                    file=file.relative_path,
                    affected_column=column,
                    evidence={
                        "category": category,
                        "occurrence_count": len(matched_values),
                        "detection_methods": methods,
                        "masked_evidence": masked_evidence,
                    },
                    message=(
                        f"Column '{column}' probably contains "
                        f"{category.replace('_', ' ')} data. This is a screening "
                        "finding, not a confirmed legal classification."
                    ),
                )
            )

    return findings


def _unique_masked_examples(values: list[str], category: str) -> list[str]:
    examples: list[str] = []
    for value in values:
        masked_value = (
            _mask_email(value)
            if category == "email_address" and EMAIL_PATTERN.fullmatch(value)
            else _mask_text(value)
        )
        if masked_value not in examples:
            examples.append(masked_value)
        if len(examples) == MAX_MASKED_EXAMPLES:
            break
    return examples


def _mask_email(value: str) -> str:
    local_part, domain = value.rsplit("@", maxsplit=1)
    domain_parts = domain.split(".")
    masked_domain = ".".join(
        _mask_text(part) if index < len(domain_parts) - 1 else part
        for index, part in enumerate(domain_parts)
    )
    return f"{_mask_text(local_part)}@{masked_domain}"


def _mask_text(value: str) -> str:
    if not value:
        return "***"
    return f"{value[0]}{'*' * max(len(value) - 1, 2)}"
