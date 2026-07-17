from pathlib import Path

import polars as pl

from app.schemas import CsvProfile


def profile_csv(file_path: str | Path) -> CsvProfile:
    """Build a deterministic profile for a CSV file without modifying it."""
    path = Path(file_path)
    data = pl.read_csv(path)

    return CsvProfile(
        file_name=path.name,
        row_count=data.height,
        column_count=data.width,
        column_names=data.columns,
        data_types={
            column: str(data_type)
            for column, data_type in zip(data.columns, data.dtypes, strict=True)
        },
        missing_value_counts={
            column: int(count)
            for column, count in data.null_count().row(0, named=True).items()
        },
        duplicate_row_count=data.height - data.unique().height,
    )
