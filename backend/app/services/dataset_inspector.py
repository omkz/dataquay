from pathlib import Path

from app.schemas import DatasetInspection, DatasetSummary, InspectedFile
from app.services.csv_profiler import profile_csv
from app.services.inspection_findings import detect_inspection_findings


def inspect_dataset(directory_path: str | Path) -> DatasetInspection:
    """Inventory a directory and profile each CSV file it contains."""
    directory = Path(directory_path)
    if not directory.is_dir():
        raise NotADirectoryError(f"Dataset directory does not exist: {directory}")

    file_paths = sorted(
        (path for path in directory.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(directory).as_posix(),
    )

    files = [
        InspectedFile(
            file_name=path.name,
            relative_path=path.relative_to(directory).as_posix(),
            extension=path.suffix.lower(),
            size_bytes=path.stat().st_size,
            csv_profile=profile_csv(path) if path.suffix.lower() == ".csv" else None,
        )
        for path in file_paths
    ]

    return DatasetInspection(
        summary=DatasetSummary(
            dataset_name=directory.name,
            total_file_count=len(files),
            csv_file_count=sum(file.csv_profile is not None for file in files),
            total_size_bytes=sum(file.size_bytes for file in files),
        ),
        files=files,
        findings=detect_inspection_findings(directory, files),
    )
