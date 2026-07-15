"""Streamlit dashboard: the BI face of the Gold layer (Phases.md Phase 5).
Read only, always - never writes to the lake (Rules R4).
"""
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # `streamlit run` doesn't support `-m`, unlike the pipeline scripts

import altair as alt
import polars as pl
import streamlit as st

from pipeline import lake_io

GOLD_LOAN_SUMMARY = REPO_ROOT / "data" / "lake" / "gold" / "gold_loan_summary"
GOLD_CALL_INSIGHTS = REPO_ROOT / "data" / "lake" / "gold" / "gold_call_insights"
DQ_AUDIT = REPO_ROOT / "data" / "lake" / "silver" / "dq_audit"

# Design.md palette
NAVY, TEAL, AMBER, RED, BG, TEXT = "#1B2A4A", "#2A9D8F", "#E9A03B", "#C1494B", "#F7F8FA", "#2B2D31"

st.set_page_config(page_title="LendingLens", layout="wide")
st.markdown(
    f"<style>.stApp {{ background-color: {BG}; color: {TEXT}; }} "
    f"h1, h2, h3 {{ color: {NAVY}; }}</style>",
    unsafe_allow_html=True,
)


def _badge(text: str, color: str) -> str:
    return (f'<span style="background:{color};color:white;padding:2px 10px;'
            f'border-radius:10px;font-size:0.85em;">{text}</span>')


def _read_with_retry(table_path: Path, retries: int = 2, backoff: float = 0.3) -> pl.DataFrame | None:
    """2 retries, short backoff, on a mid-write collision (Rules R4). None on
    total failure so the caller can fall back to last-good data instead of
    surfacing an error to the presenter."""
    for attempt in range(retries + 1):
        try:
            return lake_io.read(table_path)
        except Exception:
            if attempt < retries:
                time.sleep(backoff)
    return None


def _load_all() -> dict[str, pl.DataFrame]:
    tables = {"loan_summary": GOLD_LOAN_SUMMARY, "call_insights": GOLD_CALL_INSIGHTS, "dq_audit": DQ_AUDIT}
    last_good = st.session_state.get("data", {})
    return {
        key: (_read_with_retry(path) if _read_with_retry(path) is not None else last_good.get(key, pl.DataFrame()))
        for key, path in tables.items()
    }


st.title("LendingLens - One Curated Layer, Two Consumers")

if st.button("Refresh") or "data" not in st.session_state:
    st.session_state.data = _load_all()

loan_summary = st.session_state.data["loan_summary"]
call_insights = st.session_state.data["call_insights"]
dq_audit = st.session_state.data["dq_audit"]

# --- Row 1: metric tiles ---
total_loans = int(loan_summary["loan_count"].sum()) if loan_summary.height else 0
total_amount = float(loan_summary["total_amount"].sum()) if loan_summary.height else 0.0
calls_processed = call_insights.height
checks_total = dq_audit.height
checks_clean = dq_audit.filter(pl.col("failed_count") == 0).height if checks_total else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Loans", f"{total_loans:,}")
c2.metric("Total Amount", f"${total_amount:,.0f}")
c3.metric("Calls Processed", f"{calls_processed:,}")
c4.metric("Checks Passed", f"{checks_clean}/{checks_total}")

# --- Row 2: bar chart of loans by state, donut of loans by risk band ---
col_bar, col_donut = st.columns(2)
with col_bar:
    st.subheader("Loans by State")
    if loan_summary.height:
        by_state = loan_summary.group_by("state").agg(pl.col("loan_count").sum()).sort("state")
        chart = alt.Chart(by_state.to_pandas()).mark_bar(color=TEAL).encode(
            x=alt.X("state:N", title="State"),
            y=alt.Y("loan_count:Q", title="Loan Count"),
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No loan data yet. Run the pipeline, then click Refresh.")

with col_donut:
    st.subheader("Loans by Risk Band")
    if loan_summary.height:
        by_risk = loan_summary.group_by("risk_band").agg(pl.col("loan_count").sum())
        chart = alt.Chart(by_risk.to_pandas()).mark_arc(innerRadius=60).encode(
            theta=alt.Theta("loan_count:Q", title="Loan Count"),
            color=alt.Color("risk_band:N", title="Risk Band",
                             scale=alt.Scale(domain=["LOW", "MEDIUM", "HIGH"], range=[TEAL, AMBER, RED])),
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No loan data yet. Run the pipeline, then click Refresh.")

# --- Row 3: call insights table ---
st.subheader("Call Insights")
if call_insights.height == 0:
    st.info("No calls processed yet.")
else:
    for row in call_insights.sort("processed_at", descending=True).iter_rows(named=True):
        col_id, col_transcript, col_hardship, col_complaint = st.columns([2, 4, 1, 1])
        col_id.markdown(f"`{row['call_id']}`")
        transcript = row["transcript_masked"] or ""
        preview = transcript[:80] + ("..." if len(transcript) > 80 else "")
        with col_transcript.expander(preview or "(empty transcript)"):
            st.write(transcript)
        col_hardship.markdown(
            _badge("Hardship", RED) if row["hardship_flag"] else _badge("Clear", TEAL),
            unsafe_allow_html=True,
        )
        col_complaint.markdown(
            _badge("Complaint", RED) if row["complaint_flag"] else _badge("Clear", TEAL),
            unsafe_allow_html=True,
        )

# --- Row 4: collapsible data quality panel ---
with st.expander("Data Quality"):
    # Quarantine total is derived from dq_audit's failed_count, not a direct
    # read of the quarantine table: FR7 restricts the dashboard to Gold and
    # audit tables only.
    quarantine_total = int(dq_audit["failed_count"].sum()) if checks_total else 0
    st.markdown(f"**Quarantine total:** {quarantine_total}")
    if checks_total:
        for row in dq_audit.sort(["table", "check_name"]).iter_rows(named=True):
            ok = row["failed_count"] == 0
            status = _badge("PASS", TEAL) if ok else _badge(f"{row['failed_count']} FAILED", AMBER)
            st.markdown(f"{status} &nbsp; `{row['table']}.{row['check_name']}` "
                        f"({row['passed_count']} passed)", unsafe_allow_html=True)
    else:
        st.info("No quality checks recorded yet. Run the pipeline, then click Refresh.")
