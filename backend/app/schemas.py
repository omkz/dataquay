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


class DatasetInspection(BaseModel):
    summary: DatasetSummary
    files: list[InspectedFile]
