from pydantic import BaseModel


class CsvProfile(BaseModel):
    file_name: str
    row_count: int
    column_count: int
    column_names: list[str]
    data_types: dict[str, str]
    missing_value_counts: dict[str, int]
    duplicate_row_count: int
