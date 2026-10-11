import base64
import io

import pandas as pd
from fastapi.testclient import TestClient

from backend import app

client = TestClient(app)


def post_csv(name: str, content: bytes, **data):
    defaults = {
        "remove_duplicates": "true",
        "handle_missing": "true",
        "trim_text": "true",
        "normalize_text": "false",
        "normalize_case": "lowercase",
        "convert_numbers": "true",
        "missing_strategy": "Smart (recommended)",
    }
    defaults.update(data)
    return client.post(
        "/clean",
        files={"file": (name, io.BytesIO(content), "text/csv")},
        data=defaults,
    )


def cleaned_frame(response):
    payload = response.json()
    raw = base64.b64decode(payload["cleaned_csv_base64"])
    return payload, pd.read_csv(io.BytesIO(raw))


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_valid_csv_cleaning_and_smart_missing_value_imputation():
    response = post_csv(
        "test.csv",
        b"Name,Age,City\nArun,22,Chennai\nPriya,,Madurai\nKumar,25,Trichy\n",
    )
    assert response.status_code == 200
    result, frame = cleaned_frame(response)
    assert len(frame) == 3
    assert frame["Age"].isna().sum() == 0
    assert frame.loc[1, "Age"] == 23.5
    assert result["summary"]["missing_cells_after"] == 0


def test_duplicate_removal():
    response = post_csv("duplicates.csv", b"Name,Age\nArun,22\nArun,22\n")
    assert response.status_code == 200
    result, frame = cleaned_frame(response)
    assert len(frame) == 1
    assert result["summary"]["rows_removed"] == 1
    assert result["summary"]["duplicate_rows_after"] == 0


def test_invalid_file_extension_is_rejected():
    response = post_csv("invalid.txt", b"This is not a CSV")
    assert response.status_code == 400
    assert response.json()["detail"] == "Please upload a .csv file."


def test_zero_byte_file_is_rejected():
    response = post_csv("empty.csv", b"")
    assert response.status_code == 400
    assert response.json()["detail"] == "The uploaded file is empty."


def test_header_only_csv_is_accepted():
    response = post_csv("headers.csv", b"Name,Age,City\n")
    assert response.status_code == 200
    result, frame = cleaned_frame(response)
    assert list(frame.columns) == ["Name", "Age", "City"]
    assert len(frame) == 0
    assert result["summary"]["original_rows"] == 0
    assert result["summary"]["cleaned_rows"] == 0


def test_numeric_looking_column_is_converted_safely():
    response = post_csv(
        "numeric.csv",
        b"Name,Age\nArun,22\nPriya,23\nKumar,24\n",
    )
    assert response.status_code == 200
    result, frame = cleaned_frame(response)
    assert pd.api.types.is_numeric_dtype(frame["Age"])
    age_profile = next(column for column in result["columns"] if column["name"] == "Age")
    assert age_profile["dtype"].startswith("int") or age_profile["dtype"].startswith("float")


def test_whitespace_is_trimmed_and_duplicate_detection_runs_after_trim():
    response = post_csv(
        "spaces.csv",
        b"Name,City\n Arun , Chennai \nArun,Chennai\n",
    )
    assert response.status_code == 200
    result, frame = cleaned_frame(response)
    assert len(frame) == 1
    assert frame.loc[0, "Name"] == "Arun"
    assert frame.loc[0, "City"] == "Chennai"
    assert result["summary"]["rows_removed"] == 1


def test_unusual_unicode_characters_are_preserved():
    response = post_csv(
        "unicode.csv",
        "Name,City\nJosé,Montréal\n李雷,臺北\n🙂,Chennai\n".encode("utf-8"),
    )
    assert response.status_code == 200
    _, frame = cleaned_frame(response)
    assert frame["Name"].tolist() == ["José", "李雷", "🙂"]
    assert frame["City"].tolist() == ["Montréal", "臺北", "Chennai"]


def test_drop_missing_strategy_removes_incomplete_rows():
    response = post_csv(
        "missing.csv",
        b"Name,Age\nArun,22\nPriya,\nKumar,25\n",
        missing_strategy="Drop rows with missing values",
    )
    assert response.status_code == 200
    result, frame = cleaned_frame(response)
    assert len(frame) == 2
    assert frame["Age"].isna().sum() == 0
    assert result["summary"]["rows_removed"] == 1


def test_fill_zero_strategy():
    response = post_csv(
        "zero.csv",
        b"Name,Age\nArun,22\nPriya,\n",
        missing_strategy="Fill with 0",
    )
    assert response.status_code == 200
    _, frame = cleaned_frame(response)
    assert frame["Age"].isna().sum() == 0
    assert frame.loc[1, "Age"] == 0


def test_malformed_csv_is_rejected():
    response = post_csv(
        "malformed.csv",
        b"Name,Age\\nArun,22,unexpected-column\\n",
    )
    assert response.status_code == 400
    assert "Could not parse CSV" in response.json()["detail"]
