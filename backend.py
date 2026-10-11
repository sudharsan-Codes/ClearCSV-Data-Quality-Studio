import base64
import io
from typing import Literal

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="ClearCSV API",
    description="CSV validation, cleaning, profiling and export API for the ClearCSV Data Quality Studio.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"name": "ClearCSV API", "version": "2.0.0", "status": "online", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/clean")
async def clean_csv(
    file: UploadFile = File(...),
    remove_duplicates: bool = Form(True),
    handle_missing: bool = Form(True),
    trim_text: bool = Form(True),
    normalize_text: bool = Form(False),
    normalize_case: Literal["lowercase", "Title Case", "UPPERCASE"] = Form("lowercase"),
    convert_numbers: bool = Form(True),
    missing_strategy: Literal["Smart (recommended)", "Fill with N/A", "Fill with 0", "Drop rows with missing values"] = Form("Smart (recommended)"),
):
    filename = file.filename or "upload.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File is larger than 25 MB. Please upload a smaller CSV.")

    try:
        original = pd.read_csv(io.BytesIO(raw))
    except UnicodeDecodeError:
        try:
            original = pd.read_csv(io.BytesIO(raw), encoding="latin-1")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not decode CSV: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}")

    if original.shape[1] == 0:
        raise HTTPException(status_code=400, detail="No columns were detected in this CSV.")

    df = original.copy()
    original_rows = len(df)
    original_columns = len(df.columns)
    missing_before = int(df.isna().sum().sum())
    duplicates_before = int(df.duplicated().sum())
    rules = []

    # Work on text columns without changing the original uploaded data.
    text_columns = df.select_dtypes(include=["object", "string"]).columns.tolist()
    if trim_text and text_columns:
        for col in text_columns:
            df[col] = df[col].map(lambda value: value.strip() if isinstance(value, str) else value)
        rules.append("Trimmed leading/trailing whitespace")

    if normalize_text and text_columns:
        for col in text_columns:
            if normalize_case == "lowercase":
                df[col] = df[col].map(lambda value: value.lower() if isinstance(value, str) else value)
            elif normalize_case == "Title Case":
                df[col] = df[col].map(lambda value: value.title() if isinstance(value, str) else value)
            else:
                df[col] = df[col].map(lambda value: value.upper() if isinstance(value, str) else value)
        rules.append(f"Normalized text to {normalize_case}")

    # Convert empty/whitespace-only strings into true missing values.
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].replace(r"^\s*$", pd.NA, regex=True)

    if convert_numbers:
        for col in df.select_dtypes(include=["object", "string"]).columns:
            non_null = df[col].dropna()
            if len(non_null) > 0:
                converted = pd.to_numeric(df[col], errors="coerce")
                # Convert only if every non-empty value is numeric-looking.
                if converted[non_null.index].notna().all():
                    df[col] = converted
        rules.append("Converted numeric-looking columns where safe")

    if remove_duplicates:
        before = len(df)
        df = df.drop_duplicates()
        rules.append(f"Removed {before - len(df)} duplicate row(s)")

    if handle_missing:
        if missing_strategy == "Drop rows with missing values":
            before = len(df)
            df = df.dropna()
            rules.append(f"Dropped {before - len(df)} row(s) with missing values")
        else:
            for col in df.columns:
                if not df[col].isna().any():
                    continue
                if missing_strategy == "Fill with N/A":
                    fill_value = "N/A"
                elif missing_strategy == "Fill with 0":
                    fill_value = 0
                else:
                    # Smart strategy: median for numeric, mode for text/category.
                    if pd.api.types.is_numeric_dtype(df[col]):
                        median = df[col].median()
                        fill_value = median if pd.notna(median) else 0
                    else:
                        mode = df[col].mode(dropna=True)
                        fill_value = mode.iloc[0] if not mode.empty else "N/A"
                df[col] = df[col].fillna(fill_value)
            rules.append(f"Handled missing values ({missing_strategy})")

    output = df.to_csv(index=False).encode("utf-8-sig")
    missing_after = int(df.isna().sum().sum())
    duplicates_after = int(df.duplicated().sum())
    summary = {
        "original_rows": int(original_rows),
        "cleaned_rows": int(len(df)),
        "rows_removed": int(original_rows - len(df)),
        "original_columns": int(original_columns),
        "cleaned_columns": int(len(df.columns)),
        "missing_cells_before": missing_before,
        "missing_cells_after": missing_after,
        "duplicate_rows_before": duplicates_before,
        "duplicate_rows_after": duplicates_after,
        "cells_total_before": int(original.size),
        "completeness_before_percent": round(100 * (1 - missing_before / max(original.size, 1)), 2),
        "completeness_after_percent": round(100 * (1 - missing_after / max(df.size, 1)), 2),
    }
    columns = [
        {
            "name": str(col),
            "dtype": str(df[col].dtype),
            "missing_values": int(df[col].isna().sum()),
            "unique_values": int(df[col].nunique(dropna=True)),
        }
        for col in df.columns
    ]
    return {
        "filename": filename,
        "cleaned_csv_base64": base64.b64encode(output).decode("ascii"),
        "rules_applied": rules,
        "summary": summary,
        "columns": columns,
    }
