# ClearCSV — Data Quality Studio

A portfolio-ready CSV cleaning application built with **Streamlit, FastAPI, Pandas and Plotly**.

## Features

- CSV upload and validation (25 MB upload limit in the API)
- Original data preview and column schema
- Data quality dashboard: missing cells, duplicates, completeness and unique values
- Interactive charts for missing values and column completeness
- Configurable cleaning pipeline:
  - Remove duplicate rows
  - Trim leading/trailing whitespace
  - Normalize text to lowercase, Title Case or uppercase
  - Convert numeric-looking columns when conversion is safe
  - Handle missing values using Smart, N/A, zero or drop-row strategies
- Cleaned dataset preview
- Download cleaned CSV
- Download JSON quality report
- FastAPI health endpoint and interactive API docs
- Friendly errors for invalid uploads and backend connection failures

## Project structure

```text
CSV CLEANER TOOL/
├── frontend.py
├── backend.py
├── requirements.txt
├── README.md
└── sample.csv
```

## Run locally on Windows

Open two terminals in the project folder.

### 1. Create/activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run this for the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 2. Start FastAPI (Terminal 1)

```powershell
python -m uvicorn backend:app --reload --host 127.0.0.1 --port 8000
```

API health check: `http://127.0.0.1:8000/health`  
Interactive API docs: `http://127.0.0.1:8000/docs`

Keep this terminal open.

### 3. Start Streamlit (Terminal 2)

```powershell
python -m streamlit run frontend.py
```

Open `http://localhost:8501`.

## Quick test

Upload `sample.csv`, keep the default rules enabled, and click **Clean dataset**. Check that the preview is updated, then download the cleaned CSV and JSON quality report.

## API contract

`POST /clean` accepts a multipart CSV file and form fields for cleaning options. It returns:
- `cleaned_csv_base64`: cleaned CSV bytes encoded as Base64
- `summary`: before/after row, duplicate, missing-cell and completeness metrics
- `rules_applied`: cleaning operations applied
- `columns`: cleaned column profile

## Important notes

- The source upload is not modified on disk.
- The API rejects non-CSV uploads and files over 25 MB.
- The Smart missing-value strategy uses the median for numeric columns and the mode for non-numeric columns. Review imputed values before using them for consequential analysis.
- No database is required for this version; the processing is stateless and data is held in memory for the request/session.
- For production deployment, add authentication, rate limits, structured logging, automated tests, and private-data retention policies.

## Suggested Git workflow

Commit meaningful milestones rather than one giant commit:

```bash
git add frontend.py backend.py requirements.txt README.md
git commit -m "Build ClearCSV data quality dashboard"
git commit -am "Add configurable cleaning and quality report exports"
```
