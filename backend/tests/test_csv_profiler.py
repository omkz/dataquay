from pathlib import Path

from app.services.csv_profiler import profile_csv


def test_profile_csv_reports_shape_types_missing_values_and_duplicates(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "measurements.csv"
    csv_path.write_text(
        "sample_id,measurement,note\n"
        "S001,10.5,complete\n"
        "S002,,\n"
        "S001,10.5,complete\n",
        encoding="utf-8",
    )

    profile = profile_csv(csv_path)

    assert profile.file_name == "measurements.csv"
    assert profile.row_count == 3
    assert profile.column_count == 3
    assert profile.column_names == ["sample_id", "measurement", "note"]
    assert profile.data_types == {
        "sample_id": "String",
        "measurement": "Float64",
        "note": "String",
    }
    assert profile.missing_value_counts == {
        "sample_id": 0,
        "measurement": 1,
        "note": 1,
    }
    assert profile.duplicate_row_count == 1
