from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_inspect_sample_returns_participants_csv_profile() -> None:
    response = client.get("/api/inspect/sample")

    assert response.status_code == 200
    assert response.json() == {
        "file_name": "participants.csv",
        "row_count": 4,
        "column_count": 5,
        "column_names": [
            "participant_id",
            "name",
            "email",
            "age",
            "joined_at",
        ],
        "data_types": {
            "participant_id": "String",
            "name": "String",
            "email": "String",
            "age": "Int64",
            "joined_at": "String",
        },
        "missing_value_counts": {
            "participant_id": 0,
            "name": 0,
            "email": 1,
            "age": 1,
            "joined_at": 0,
        },
        "duplicate_row_count": 0,
    }
