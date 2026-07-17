from pathlib import Path

from app.services.dataset_inspector import inspect_dataset


def test_inspect_dataset_inventories_files_and_profiles_only_csv_files(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "example-dataset"
    nested_path = dataset_path / "tables"
    nested_path.mkdir(parents=True)

    readme_path = dataset_path / "README.md"
    readme_path.write_text("# Example dataset\n", encoding="utf-8")
    csv_path = nested_path / "measurements.csv"
    csv_path.write_text(
        "sample_id,value\nS001,12\nS002,\n",
        encoding="utf-8",
    )

    inspection = inspect_dataset(dataset_path)

    assert inspection.summary.dataset_name == "example-dataset"
    assert inspection.summary.total_file_count == 2
    assert inspection.summary.csv_file_count == 1
    assert inspection.summary.total_size_bytes == (
        readme_path.stat().st_size + csv_path.stat().st_size
    )

    assert [file.relative_path for file in inspection.files] == [
        "README.md",
        "tables/measurements.csv",
    ]

    readme = inspection.files[0]
    assert readme.file_name == "README.md"
    assert readme.extension == ".md"
    assert readme.size_bytes == readme_path.stat().st_size
    assert readme.csv_profile is None

    measurements = inspection.files[1]
    assert measurements.file_name == "measurements.csv"
    assert measurements.extension == ".csv"
    assert measurements.size_bytes == csv_path.stat().st_size
    assert measurements.csv_profile is not None
    assert measurements.csv_profile.row_count == 2
    assert measurements.csv_profile.column_count == 2
    assert measurements.csv_profile.missing_value_counts == {
        "sample_id": 0,
        "value": 1,
    }


def test_inspect_dataset_detects_quality_and_reference_findings(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "linked-dataset"
    dataset_path.mkdir()
    (dataset_path / "participants.csv").write_text(
        "participant_id,name\n"
        "P001,Alice\n"
        "P001,\n",
        encoding="utf-8",
    )
    (dataset_path / "observations.csv").write_text(
        "observation_id,participant_id,value\n"
        "O001,P001,12\n"
        "O002,P999,20\n"
        "O002,P999,20\n",
        encoding="utf-8",
    )

    inspection = inspect_dataset(dataset_path)
    findings = {
        (finding.type.value, finding.file, finding.affected_column): finding
        for finding in inspection.findings
    }

    missing_name = findings[("missing_values", "participants.csv", "name")]
    assert missing_name.severity.value == "medium"
    assert missing_name.evidence == {"missing_count": 1}

    duplicate_rows = findings[("duplicate_rows", "observations.csv", None)]
    assert duplicate_rows.evidence == {"duplicate_row_count": 1}

    duplicate_participant = findings[
        ("duplicate_identifier_values", "participants.csv", "participant_id")
    ]
    assert duplicate_participant.severity.value == "high"
    assert duplicate_participant.evidence == {
        "duplicate_count": 1,
        "duplicate_values": ["P001"],
    }

    duplicate_observation = findings[
        ("duplicate_identifier_values", "observations.csv", "observation_id")
    ]
    assert duplicate_observation.evidence["duplicate_values"] == ["O002"]

    missing_reference = findings[
        ("missing_reference", "observations.csv", "participant_id")
    ]
    assert missing_reference.severity.value == "high"
    assert missing_reference.evidence == {
        "referenced_file": "participants.csv",
        "missing_values": ["P999"],
        "reference_count": 2,
    }

    assert all(finding.message for finding in inspection.findings)
