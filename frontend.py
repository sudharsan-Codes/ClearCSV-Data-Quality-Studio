import io
import json
import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(
    page_title="ClearCSV | Data Quality Studio",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_API_URL = os.getenv("BACKEND_API_URL", "https://clearcsv-api.onrender.com").strip().rstrip("/")
API_URL = st.sidebar.text_input("Backend API URL", value=DEFAULT_API_URL).strip().rstrip("/")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root { --ink:#eaf0ff; --muted:#98a6c7; --panel:#151c2d; --line:#28334b; --accent:#8b7cff; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background: radial-gradient(ellipse at 15% 0%, #20294a 0%, #0b1020 42%, #090d18 100%); color:var(--ink); }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#151b2d,#0e1423); border-right:1px solid var(--line); }
h1,h2,h3 { font-family:'Space Grotesk',sans-serif !important; letter-spacing:-.03em; }
.hero { padding:1.35rem 1.5rem; border:1px solid #34405e; border-radius:22px; background:linear-gradient(120deg,rgba(139,124,255,.18),rgba(41,198,180,.07)); margin-bottom:1rem; }
.eyebrow { color:#9e96ff; text-transform:uppercase; font-size:.76rem; letter-spacing:.16em; font-weight:700; }
.hero-title { font-size:2.25rem; font-weight:700; line-height:1.1; margin:.35rem 0 .5rem; }
.hero-sub { color:#aebbd7; max-width:760px; }
.metric { border:1px solid var(--line); background:rgba(21,28,45,.88); padding:1rem 1.1rem; border-radius:16px; min-height:112px; }
.metric-label { color:#9eacc9; font-size:.83rem; }
.metric-value { font-family:'Space Grotesk',sans-serif; font-size:1.8rem; font-weight:700; margin-top:.25rem; }
.metric-note { color:#7ddbc8; font-size:.78rem; margin-top:.15rem; }
.section-label { color:#a8b5d3; text-transform:uppercase; font-size:.75rem; letter-spacing:.12em; font-weight:700; margin:1.1rem 0 .45rem; }
div[data-testid="stDataFrame"] { border:1px solid #2a354d; border-radius:12px; overflow:hidden; }
.stButton button, .stDownloadButton button { border-radius:10px; font-weight:700; min-height:2.7rem; }
div[data-testid="stFileUploader"] { border:1px dashed #59658a; background:rgba(23,31,51,.65); border-radius:16px; padding:.5rem; }
.small-muted { color:#9eacc9; font-size:.88rem; }
.stAlert { border-radius:12px; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🧹 ClearCSV")
    st.caption("DATA QUALITY STUDIO")
    st.markdown("---")
    st.markdown("### Cleaning rules")
    remove_duplicates = st.toggle("Remove duplicate rows", value=True)
    handle_missing = st.toggle("Handle missing values", value=True)
    trim_text = st.toggle("Trim text whitespace", value=True)
    normalize_text = st.toggle("Normalize text case", value=False)
    normalize_case = st.selectbox("Text case", ["lowercase", "Title Case", "UPPERCASE"], disabled=not normalize_text)
    convert_numbers = st.toggle("Convert numeric-looking columns", value=True)
    missing_strategy = st.selectbox(
        "Missing-value strategy",
        ["Smart (recommended)", "Fill with N/A", "Fill with 0", "Drop rows with missing values"],
        disabled=not handle_missing,
    )
    st.markdown("---")
    st.markdown("### About")
    st.caption("A portfolio-ready CSV cleaning workflow built with Streamlit, FastAPI and Pandas.")
    st.caption("Upload → configure → inspect → clean → export")

st.markdown("""
<div class="hero">
  <div class="eyebrow">CSV WORKSPACE · v2.0</div>
  <div class="hero-title">Make messy data <span style="color:#9e96ff">analysis-ready.</span></div>
  <div class="hero-sub">Upload a CSV, choose your cleaning rules, inspect data quality, and export a cleaned dataset with a clear before-and-after report.</div>
</div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"], help="CSV only · Keep your original file unchanged")

def metric_card(label, value, note=""):
    st.markdown(
        f'<div class="metric"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>',
        unsafe_allow_html=True,
    )

def csv_bytes(frame):
    return frame.to_csv(index=False).encode("utf-8-sig")

if uploaded_file is None:
    st.info("👆 Upload a CSV file to start. You can use your existing sample.csv for a quick demo.")
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("SMART CLEANING", "01", "Choose exactly which rules to apply")
    with c2:
        metric_card("QUALITY REPORT", "02", "Review nulls, duplicates and row changes")
    with c3:
        metric_card("EXPORT READY", "03", "Download cleaned CSV and JSON report")
    st.stop()

try:
    original_bytes = uploaded_file.getvalue()
    original_df = pd.read_csv(io.BytesIO(original_bytes))
    if original_df.empty and len(original_df.columns) == 0:
        st.error("The uploaded CSV is empty.")
        st.stop()
except Exception as exc:
    st.error(f"Could not read this CSV: {exc}")
    st.stop()

if original_df.shape[1] == 0:
    st.error("No columns were found. Please upload a valid CSV file.")
    st.stop()

# Keep an in-memory preview and use the API for the actual cleaning operation.
null_count = int(original_df.isna().sum().sum())
duplicate_count = int(original_df.duplicated().sum())
memory_kb = original_df.memory_usage(deep=True).sum() / 1024

st.markdown('<div class="section-label">Dataset overview</div>', unsafe_allow_html=True)
m1, m2, m3, m4 = st.columns(4)
with m1: metric_card("ROWS", f"{len(original_df):,}", "Records in source file")
with m2: metric_card("COLUMNS", f"{len(original_df.columns):,}", "Fields detected")
with m3: metric_card("MISSING CELLS", f"{null_count:,}", f"{(null_count / max(original_df.size, 1))*100:.1f}% of all cells")
with m4: metric_card("DUPLICATE ROWS", f"{duplicate_count:,}", f"{memory_kb:.1f} KB in memory")

tab_data, tab_quality, tab_clean = st.tabs(["📄 Source preview", "🔎 Data quality", "✨ Clean & export"])

with tab_data:
    st.markdown("### Original CSV data")
    st.caption(f"Showing up to 500 rows · {uploaded_file.name}")
    st.dataframe(original_df.head(500), use_container_width=True, height=330)
    with st.expander("Inspect column types"):
        schema = pd.DataFrame({
            "Column": original_df.columns.astype(str),
            "Data type": [str(t) for t in original_df.dtypes],
            "Missing values": original_df.isna().sum().values,
            "Unique values": [original_df[c].nunique(dropna=True) for c in original_df.columns],
        })
        st.dataframe(schema, use_container_width=True, hide_index=True)

with tab_quality:
    st.markdown("### Data quality profile")
    q1, q2 = st.columns(2)
    missing_by_column = original_df.isna().sum().rename("Missing values").reset_index()
    missing_by_column.columns = ["Column", "Missing values"]
    with q1:
        st.markdown("**Missing values by column**")
        if missing_by_column["Missing values"].sum() > 0:
            fig = px.bar(missing_by_column, x="Column", y="Missing values", color="Missing values",
                         color_continuous_scale=["#4fd1c5", "#8b7cff"], template="plotly_dark")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False, margin=dict(l=5,r=5,t=20,b=5))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("No missing values detected.")
    with q2:
        st.markdown("**Column completeness**")
        completeness = (1 - original_df.isna().mean()).mul(100).rename("Completeness %").reset_index()
        completeness.columns = ["Column", "Completeness %"]
        fig2 = px.bar(completeness, x="Column", y="Completeness %", range_y=[0, 100],
                      color="Completeness %", color_continuous_scale=["#ff8f8f", "#4fd1c5"], template="plotly_dark")
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False, margin=dict(l=5,r=5,t=20,b=5))
        st.plotly_chart(fig2, use_container_width=True)
    st.markdown("**Column profile**")
    st.dataframe(schema if "schema" in locals() else pd.DataFrame({
        "Column": original_df.columns.astype(str),
        "Data type": [str(t) for t in original_df.dtypes],
        "Missing values": original_df.isna().sum().values,
        "Unique values": [original_df[c].nunique(dropna=True) for c in original_df.columns],
    }), use_container_width=True, hide_index=True)

with tab_clean:
    st.markdown("### Run cleaning pipeline")
    st.write("The selected rules will be sent to the FastAPI backend for processing.")
    if st.button("✨ Clean dataset", type="primary", use_container_width=True):
        data = {
            "remove_duplicates": str(remove_duplicates).lower(),
            "handle_missing": str(handle_missing).lower(),
            "trim_text": str(trim_text).lower(),
            "normalize_text": str(normalize_text).lower(),
            "normalize_case": normalize_case,
            "convert_numbers": str(convert_numbers).lower(),
            "missing_strategy": missing_strategy,
        }
        try:
            with st.spinner("Cleaning your dataset…"):
                response = requests.post(
                    f"{API_URL}/clean",
                    files={"file": (uploaded_file.name, original_bytes, "text/csv")},
                    data=data,
                    timeout=120,
                )
            if response.status_code != 200:
                try:
                    detail = response.json().get("detail", response.text)
                except Exception:
                    detail = response.text
                st.error(f"Backend returned {response.status_code}: {detail}")
            else:
                result = response.json()
                cleaned_bytes = __import__("base64").b64decode(result["cleaned_csv_base64"])
                cleaned_df = pd.read_csv(io.BytesIO(cleaned_bytes))
                st.session_state["clean_result"] = result
                st.session_state["cleaned_bytes"] = cleaned_bytes
                st.session_state["cleaned_df"] = cleaned_df
                st.session_state["source_name"] = uploaded_file.name
                st.success("Cleaning completed successfully.")
        except requests.exceptions.ConnectionError:
            st.error(f"Could not connect to {API_URL}. Start the backend in a second terminal with: python -m uvicorn backend:app --reload --port 8000")
        except requests.exceptions.Timeout:
            st.error("The cleaning request timed out. Try a smaller CSV file.")
        except Exception as exc:
            st.error(f"Cleaning failed: {exc}")

if "clean_result" in st.session_state and st.session_state.get("source_name") == uploaded_file.name:
    result = st.session_state["clean_result"]
    cleaned_df = st.session_state["cleaned_df"]
    cleaned_bytes = st.session_state["cleaned_bytes"]
    st.markdown("---")
    st.markdown("### ✅ Cleaned dataset")
    before_rows = result["summary"]["original_rows"]
    after_rows = result["summary"]["cleaned_rows"]
    removed_rows = result["summary"]["rows_removed"]
    a, b, c, d = st.columns(4)
    with a: metric_card("ROWS BEFORE", f"{before_rows:,}")
    with b: metric_card("ROWS AFTER", f"{after_rows:,}", "Ready for analysis")
    with c: metric_card("ROWS REMOVED", f"{removed_rows:,}", "Duplicates / missing rows")
    with d: metric_card("MISSING CELLS AFTER", f'{result["summary"]["missing_cells_after"]:,}')
    st.dataframe(cleaned_df.head(500), use_container_width=True, height=300)

    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            "⬇️ Download cleaned CSV",
            data=cleaned_bytes,
            file_name=f"{uploaded_file.name.rsplit('.', 1)[0]}_cleaned.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_file": uploaded_file.name,
        "rules_applied": result["rules_applied"],
        "summary": result["summary"],
        "columns": result["columns"],
    }
    with dl2:
        st.download_button(
            "📋 Download quality report (JSON)",
            data=json.dumps(report, indent=2).encode("utf-8"),
            file_name=f"{uploaded_file.name.rsplit('.', 1)[0]}_quality_report.json",
            mime="application/json",
            use_container_width=True,
        )
    with st.expander("View cleaning report"):
        st.json(report)

st.markdown("---")
st.caption("ClearCSV · Streamlit + FastAPI + Pandas + Plotly · Built for transparent, repeatable data cleaning.")
