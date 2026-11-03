from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from volvewatch.analytics import flag_anomalies, forecast_well, prepare_production_data

st.set_page_config(page_title="VolveWatch", page_icon="🛢️", layout="wide")
st.title("VolveWatch")
st.caption("Well-level production monitoring, trend forecasting, and investigation flags")
st.info(
    "Upload a Volve production CSV or workbook and map its columns below. The dashboard analyzes only "
    "the data you provide; it does not bundle fabricated production records."
)

upload = st.file_uploader("Production data (CSV or Excel workbook)", type=["csv", "xlsx"])
if upload is None:
    st.markdown(
        "### Start with your production export\n"
        "Choose a CSV or Excel workbook containing a date, a well identifier, and one numeric "
        "production measure. You can map the actual column names after upload. Keep the source "
        "dataset and its data dictionary alongside the export so units and reporting frequency stay clear."
    )
    st.stop()

try:
    uploaded_bytes = upload.getvalue()
    if upload.name.lower().endswith(".xlsx"):
        workbook = pd.ExcelFile(BytesIO(uploaded_bytes))
        sheet_name = st.selectbox("Workbook sheet", workbook.sheet_names)
        raw = pd.read_excel(BytesIO(uploaded_bytes), sheet_name=sheet_name)
        lower_columns = {str(column).strip().lower(): column for column in raw.columns}
        year_column = next((column for name, column in lower_columns.items() if name in {"year", "yearprd"}), None)
        month_column = next((column for name, column in lower_columns.items() if name in {"month", "monthprd"}), None)
        has_date = any("date" in str(column).lower() for column in raw.columns)
        if not has_date and year_column is not None and month_column is not None:
            years = pd.to_numeric(raw[year_column], errors="coerce")
            months = pd.to_numeric(raw[month_column], errors="coerce")
            valid_period = years.notna() & months.notna()
            raw = raw.loc[valid_period].copy()
            raw["ProductionDate"] = pd.to_datetime(
                {"year": years.loc[valid_period].astype(int),
                 "month": months.loc[valid_period].astype(int),
                 "day": 1},
                errors="coerce",
            )
    else:
        raw = pd.read_csv(BytesIO(uploaded_bytes), sep=None, engine="python")
except Exception as exc:
    st.error(f"Could not read this production file: {exc}")
    st.stop()

if raw.empty or len(raw.columns) < 3:
    st.error("The selected sheet needs a date (or year and month), a well identifier, and a production measure.")
    st.stop()

columns = list(raw.columns)
def guess_column(words: tuple[str, ...], fallback: int) -> str:
    return next((c for c in columns if any(word in str(c).lower() for word in words)), columns[min(fallback, len(columns) - 1)])

numeric_columns = [c for c in columns if pd.to_numeric(raw[c], errors="coerce").notna().any()]
left, mid, right = st.columns(3)
with left:
    date_column = st.selectbox("Date column", columns, index=columns.index(guess_column(("date", "time"), 0)))
with mid:
    well_column = st.selectbox("Well column", columns, index=columns.index(guess_column(("well", "bore", "wellbore"), 1)))
with right:
    if not numeric_columns:
        st.error("No numeric columns were found. Check that the CSV includes a production measure.")
        st.stop()
    value_guess = next((c for c in numeric_columns if any(w in str(c).lower() for w in ("oil", "gas", "water", "prod", "volume", "rate"))), numeric_columns[0])
    value_column = st.selectbox("Production measure", numeric_columns, index=numeric_columns.index(value_guess))

settings_left, settings_right = st.columns([1, 3])
with settings_left:
    aggregation = st.selectbox("Combine repeated well/date rows", ["sum", "mean"], help="Use sum for separate production volumes; use mean when repeated rows are measurements of the same rate.")
    unit = st.text_input("Measure unit (optional)", placeholder="e.g. Sm³/day")
try:
    data, quality = prepare_production_data(raw, date_column, well_column, value_column, aggregation)
except (ValueError, TypeError) as exc:
    st.error(str(exc))
    st.stop()

min_date, max_date = data["date"].min().date(), data["date"].max().date()
with settings_right:
    selected_range = st.date_input("Analysis date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
if isinstance(selected_range, tuple) and len(selected_range) == 2:
    start_date, end_date = selected_range
else:
    start_date, end_date = min_date, max_date
view = data[data["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))].copy()
if view.empty:
    st.warning("There are no observations in the selected date range.")
    st.stop()

unit_suffix = f" {unit}" if unit.strip() else ""
latest_date = view["date"].max()
latest_total = view.loc[view["date"].eq(latest_date), "production"].sum()
first_total = view.loc[view["date"].eq(view["date"].min()), "production"].sum()
change = ((latest_total - first_total) / abs(first_total) * 100) if first_total else None
k1, k2, k3, k4 = st.columns(4)
k1.metric("Wells", f"{view['well'].nunique():,}")
k2.metric("Observations", f"{len(view):,}")
k3.metric(f"Latest date total{unit_suffix}", f"{latest_total:,.3g}")
k4.metric("First-to-last date change", f"{change:+.1f}%" if change is not None else "—")

summary = view.groupby("well", as_index=False).agg(
    total_production=("production", "sum"),
    average_observation=("production", "mean"),
    latest_production=("production", "last"),
    observation_count=("production", "size"),
)
summary = summary.sort_values("total_production", ascending=False)
trends = view.groupby("date", as_index=False)["production"].sum().set_index("date")

overview_tab, well_tab, forecast_tab, quality_tab = st.tabs(["Overview", "Well detail", "Forecast & flags", "Data quality"])
with overview_tab:
    st.subheader("Production trend")
    st.line_chart(trends, y="production", height=300)
    a, b = st.columns([2, 3])
    with a:
        st.subheader("Production by well")
        st.bar_chart(summary.set_index("well")["total_production"].head(20), height=350)
    with b:
        st.subheader("Well-level summary")
        display_summary = summary.copy()
        display_summary.columns = ["Well", f"Total{unit_suffix}", f"Average / observation{unit_suffix}", f"Latest{unit_suffix}", "Observations"]
        st.dataframe(display_summary, use_container_width=True, hide_index=True)

with well_tab:
    selected_well = st.selectbox("Choose a well", sorted(view["well"].unique()))
    well_data = view[view["well"].eq(selected_well)].sort_values("date")
    st.line_chart(well_data.set_index("date")[["production"]], height=350)
    st.dataframe(well_data, use_container_width=True, hide_index=True)

with forecast_tab:
    st.subheader("Trend baseline")
    st.caption("A straight-line fit over the most recent 90 observations, projected for the selected number of reporting periods. This is a simple reference forecast, not a validated reservoir model.")
    forecast_well_name = st.selectbox("Forecast well", sorted(view["well"].unique()), key="forecast_well")
    forecast_periods = st.slider("Future reporting periods", min_value=1, max_value=90, value=14)
    history = view[view["well"].eq(forecast_well_name)].sort_values("date")
    projection = forecast_well(history, forecast_periods)
    chart_history = history[["date", "production"]].rename(columns={"production": "Observed"}).set_index("date")
    chart_projection = projection.rename(columns={"forecast": "Trend forecast"}).set_index("date")
    st.line_chart(pd.concat([chart_history, chart_projection], axis=1), height=350)
    st.dataframe(projection, use_container_width=True, hide_index=True)

    flagged = flag_anomalies(view)
    alerts = flagged[flagged["is_anomaly"]].sort_values("anomaly_score", ascending=False)
    st.subheader("Investigation flags")
    st.caption("Flags are large deviations from a centered 7-observation rolling median within each well. Review flagged records against operating context before drawing conclusions.")
    st.metric("Flagged observations", f"{len(alerts):,}")
    if alerts.empty:
        st.success("No observations crossed the current statistical threshold in this date range.")
    else:
        st.dataframe(alerts.head(100), use_container_width=True, hide_index=True)

with quality_tab:
    st.subheader("Import and cleaning summary")
    quality_rows = pd.DataFrame([
        ("Input rows", quality.input_rows),
        ("Valid observations after aggregation", quality.output_rows),
        ("Rows with invalid dates", quality.invalid_date_rows),
        ("Rows with missing well identifiers", quality.invalid_well_rows),
        ("Rows with invalid production values", quality.invalid_value_rows),
        ("Extra rows combined at duplicate well/date pairs", quality.aggregated_duplicate_rows),
    ], columns=["Check", "Count"])
    st.dataframe(quality_rows, use_container_width=True, hide_index=True)
    st.download_button("Download cleaned observations", data=data.to_csv(index=False).encode("utf-8"), file_name="volvewatch_cleaned.csv", mime="text/csv")
