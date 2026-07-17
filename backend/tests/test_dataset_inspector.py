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
