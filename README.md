# VolveWatch

VolveWatch is a local Streamlit MVP for exploring real Volve field production exports. It maps the dataset's own date, well, and measure columns, then provides field-level production trends, well comparisons, a simple trend forecast, and statistical investigation flags.

## Current scope

- Upload a CSV or Excel workbook and map its date, well, and production-measure columns. Excel workbooks can be explored one sheet at a time; monthly sheets with `Year` and `Month` fields get a month-start date column automatically.
- Parse dates and numeric values, report invalid rows, and combine repeated well/date records using a selectable sum or mean.
- Compare well totals and observation averages; inspect a selected well's time series.
- Project a straight-line baseline from up to the latest 90 observations.
- Flag large deviations from a centered rolling median for review.
- Download the cleaned well/date observations.

`data/Volve production data.xlsx` contains the copied Volve production workbook. The dashboard reads it locally and does not generate replacement production records. Confirm the selected measure and its units against the workbook metadata before interpreting totals. The forecast is a simple reference line, not a validated reservoir or decline-curve model. Statistical flags are investigation prompts, not confirmed operating anomalies.

## Run locally

Requires Python 3.10 or newer.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
streamlit run app.py
```

Open the local URL printed by Streamlit, upload `data/Volve production data.xlsx`, choose `Daily Production Data` or `Monthly Production Data`, then map the columns. The daily sheet uses `DATEPRD`, a well field such as `WELL_BORE_CODE`, and a measure such as `BORE_OIL_VOL`; the monthly sheet builds dates from `Year` and `Month` and has `Wellbore name` plus measures such as `Oil`, `Gas`, or `Water`. The synthetic CSV remains available for a clearly labeled interface walkthrough. For repeated records with separate volume components, use `sum`; for repeated measurements of the same rate, use `mean`.

## Data handling

The CSV or Excel workbook is processed locally by the Streamlit app. VolveWatch does not send data to a hosted service, persist uploads, or bundle confidential data. Keep the data dictionary and original units available for a defensible demonstration.

## Try the interface without field data

Upload `data/synthetic_production_demo.csv` to explore the dashboard. This is generated illustrative data, not Volve data; its well IDs, values, and planted spike must not be presented as real results. The companion `data/README.md` describes the fixture. Use the dataset's `report_date`, `well_id`, and a selected rate column in the mapping controls. The file includes malformed rows to show how data-quality counts behave.


## Data source and attribution

The real production workbook in `data/` is from the Equinor Volve field data release. Cite Equinor and the former Volve license partners, link the [official Volve data page](https://www.equinor.com/energy/volve-data-sharing) and [data terms](https://www.equinor.com/content/dam/statoil/documents/what-we-do/Equinor-HRS-Terms-and-conditions-for-licence-to-data-Volve.pdf), and do not present the results as endorsed by Equinor. The data terms permit use and sharing with attribution, prohibit selling the licensed material, and prohibit misleading or distorted presentation.
