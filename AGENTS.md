# AGENTS.md

Research repo (not a software package) analysing **AIS-derived fishing effort** for an
Indian Ocean paper. Pipeline: `notebooks/01` → `02` → `03_fishing_effort_trends`;
`research_paper/` holds the Springer Nature manuscript. No tests, linter, or CI — do not invent them.

## Environment

- [uv](https://docs.astral.sh/uv/) project, `requires-python >= 3.14`.
- **`.venv/` is broken**: it contains only `Scripts/python.exe` (a copy of `py.exe`), with no
  `pyvenv.cfg` or site-packages. `uv run ...` fails with `failed to locate pyvenv.cfg`.
  Recreate it with `uv venv` (or delete `.venv/` and let uv re-create it), then `uv sync`.
- Always invoke Python via uv: `uv run python ...`, `uv run jupyter lab`. Never use bare `python`.
- **`scipy` is imported by `03_fishing_effort_trends.ipynb` but is missing from `pyproject.toml`
  and `uv.lock`** (`from scipy.stats import linregress, spearmanr`). Add it before trusting a
  clean environment.
- For throwaway inspection without repairing `.venv`, use
  `uv run --isolated --with pandas --with pyarrow python -c "..."`.
- `pyproject.toml`, `uv.lock`, and `notebooks/03_data_trend_analysis.ipynb` are currently untracked.
  `git add` them if committing the environment or that notebook.

## Running things — cwd matters

Raw data (`AIS/`) is gitignored and **not present**. Without downloading it from
<https://globalfishingwatch.org/>, every `DATA_ROOT`/data-read cell fails.

- `ais_profile.py` uses repo-root-relative `DATA_ROOT = AIS/Data/Yearly` → run from repo root:
  `uv run python ais_profile.py`. Writes `ais_file_summary.csv`.
- Notebooks use `Path("../AIS/...")` / `Path("../outputs/...")` → run Jupyter with **cwd =
  `notebooks/`**. Launching from the repo root breaks every path.
- Pipeline order:
  1. `01_data_exploration_cleaning.ipynb` → `outputs/processed/ais_cleaned.parquet` (plus an
     ignored CSV copy).
  2. `02_spatiotemporal_analysis.ipynb` → `outputs/analysis/{monthly_cell,yearly_cell,spatial_summary}.parquet`
     (plus ignored summary CSVs).
  3. `03_fishing_effort_trends.ipynb` reads `monthly_cell.parquet` (falls back to recomputing from
     the cleaned parquet) → `cell_effort_trends.parquet` + `annual_cell_effort_2015_2024.parquet`,
     plus an ignored `trend_class_summary.csv`.
- `03_fishing_effort_trends.ipynb` is the canonical trend analysis.
  `03_data_trend_analysis.ipynb` is an uncommitted one-off January 2018–2024 cartopy panel that
  writes `outputs/processed/january_comparison.png`; `test.ipynb` is scratch.

## Data quirks (the important part)

The `cell_ll_lat` / `cell_ll_lon` values are **grid keys, not vessel positions**: each pair is the
lower-left corner of a 0.1° × 0.1° cell, and the recorded effort covers that whole cell.
- Scatter/map points are cell origins; never claim a vessel was "at" a lat/lon to sub-cell precision.
- Distance, density, and nearest-neighbour reasoning must account for the 0.1° cell size.

Raw monthly filenames are inconsistent: 2012–2016 use `fYYYY_M.csv`; 2017–2024 use `YYYY_M.csv`;
some are uppercase `.CSV` (2019, 2020). Each year also has an annual aggregate `YYYY.csv` that
**must be excluded** (it duplicates monthly rows). Some monthly files lack headers — notebook 01
sniffs per file (`has_expected_header`) and re-reads with `header=None, names=EXPECTED_COLUMNS`.

> **Known drift:** `01`'s `MONTHLY_PATTERN` is `^f(\d{4})_(\d{1,2})\.csv$`, matching only 2012–2016.
> The committed `ais_cleaned.parquet` nevertheless contains **2012–2024** (730,488 rows, 1,930
> vessels, 23,846 cells). Re-running notebook 01 today silently shrinks it to **5,283 rows**.
> Fix the pattern (optional `f`, any case, still reject bare `YYYY.csv`) before trusting a re-run.

Column naming drifts too: the profiler expects `cell_ll_long`; the notebooks use `cell_ll_lon`.
`ais_profile.clean_columns` does not alias them, so the profiler will report a missing column.

Missing months are **not** filled with zero: absence of AIS data ≠ zero effort; leave gaps as NaN.
`hours` is vessel-hours and `fishing_hours` ≤ `hours`; guard `fishing_ratio` against zero. Annual
unique vessels must be recomputed with `nunique`, not by summing monthly `active_vessels` (that
double-counts vessels seen in several months). Notebook 02 only aggregates; trend testing belongs
to `03_fishing_effort_trends`.

## Outputs and git

- Committed data: `outputs/processed/ais_cleaned.parquet` and the parquet files in
  `outputs/analysis/`. Observation grain is date × `cell_ll_lat` × `cell_ll_lon` × `mmsi`, plus
  derived `year`/`month`/`day` and `file_year`/`file_month` provenance.
- `cell_effort_trends.parquet` has one row per examined cell (8,697 current cells), including
  `trend_class == "Insufficient data"`; filter it before computing eligible-cell shares.
- `.gitignore` excludes **all** `*.csv` except `ais_file_summary.csv`, so notebook CSV exports are
  silently untracked. Use parquet for anything that must persist.
- `.gitignore` also excludes LaTeX build products and `*.pdf`; `research_paper/figures/*.png` are
  tracked.

## Manuscript

- Springer Nature template (`sn-jnl.cls`, `sn-mathphys-num` class option). Build from
  `research_paper/` with `latexmk -pdf sn-article.tex` (or `pdflatex` → `bibtex` → `pdflatex` ×2).
- Numbers and tables in `sn-article.tex` are **hand-copied from `03_fishing_effort_trends`**, not
  generated. If you change thresholds or rerun it, update the manuscript. Current conventions:
  trend period 2015–2024, ≥3 observed months per cell-year, ≥5 annual observations per cell,
  OLS p < 0.05 on mean monthly fishing hours.
- `research_paper/figures/cell_<lat>_<lon>.png` are static committed snapshots; none of the
  notebooks save them, so regenerate manually if the underlying trends change.

Interpretation boundary: these data measure **AIS-derived fishing effort**, not biomass, catch, or
biological productivity. Do not claim that declining effort proves declining fish productivity.
