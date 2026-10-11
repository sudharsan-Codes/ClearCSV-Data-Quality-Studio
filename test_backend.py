import io
import base64

import pandas as pd
from fastapi.testclient import TestClient

from backend import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_valid_csv_cleaning():
    csv_data = (
        b"Name,Age,City\n"
        b"Arun,22,Chennai\n"
        b"Priya,,Madurai\n"
        b"Kumar,25,Trichy\n"
    )

    response = client.post(
        "/clean",
        files={
            "file": (
                "test.csv",
                io.BytesIO(csv_data),
                "text/csv",
            )
        },
        data={
            "remove_duplicates": "true",
            "handle_missing": "true",
            "trim_text": "true",
            "normalize_text": "false",
            "normalize_case": "lowercase",
            "convert_numbers": "true",
            "missing_strategy": "Smart (recommended)",
        },
    )

    assert response.status_code == 200

    result = response.json()
    cleaned_bytes = base64.b64decode(
        result["cleaned_csv_base64"]
    )
    cleaned_df = pd.read_csv(io.BytesIO(cleaned_bytes))

    assert len(cleaned_df) == 3
    assert cleaned_df["Age"].isna().sum() == 0
    assert cleaned_df.loc[1, "Age"] == 23.5


def test_duplicate_removal():
    csv_data = (
        b"Name,Age\n"
        b"Arun,22\n"
        b"Arun,22\n"
    )

    response = client.post(
        "/clean",
        files={
            "file": (
                "duplicates.csv",
                io.BytesIO(csv_data),
                "text/csv",
            )
        },
        data={
            "remove_duplicates": "true",
            "handle_missing": "true",
            "trim_text": "true",
            "normalize_text": "false",
            "normalize_case": "lowercase",
            "convert_numbers": "true",
            "missing_strategy": "Smart (recommended)",
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["summary"]["original_rows"] == 2
    assert result["summary"]["cleaned_rows"] == 1
    assert result["summary"]["rows_removed"] == 1


def test_invalid_file_type():
    response = client.post(
        "/clean",
        files={
            "file": (
                "invalid.txt",
                b"This is not a CSV",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Please upload a .csv file."


def test_empty_file():
    response = client.post(
        "/clean",
        files={
            "file": (
                "empty.csv",
                b"",
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "The uploaded file is empty."