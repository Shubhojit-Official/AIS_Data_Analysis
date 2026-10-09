
from pathlib import Path
import pandas as pd
import numpy as np

# ============================================================
# AIS DATA PROFILER
# ============================================================
# Change this to your AIS/Data/Yearly directory.
DATA_ROOT = Path(r"AIS/Data/Yearly")

EXPECTED_COLUMNS = {
    "date",
    "cell_ll_lat",
    "cell_ll_long",
    "mmsi",
    "hours",
    "fishing_hours",
}


def clean_columns(df):
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", "_", regex=True)
    )
    return df


def profile_file(path):
    print("\n" + "=" * 80)
    print(f"FILE: {path}")
    print("=" * 80)

    try:
        df = pd.read_csv(path)
    except Exception as e:
        print(f"ERROR reading file: {e}")
        return None

    df = clean_columns(df)

    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")
    print(f"Columns: {list(df.columns)}")

    missing_expected = EXPECTED_COLUMNS - set(df.columns)
    extra = set(df.columns) - EXPECTED_COLUMNS

    if missing_expected:
        print(f"WARNING - missing expected columns: {sorted(missing_expected)}")
    if extra:
        print(f"Extra columns: {sorted(extra)}")

    if "date" in df.columns:
        dates = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        print(f"Invalid dates: {dates.isna().sum():,}")
        if dates.notna().any():
            print(f"Date range: {dates.min().date()} -> {dates.max().date()}")

    for col in ["cell_ll_lat", "cell_ll_long", "hours", "fishing_hours"]:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce")
            print(
                f"{col}: missing={values.isna().sum():,}, "
                f"min={values.min()}, max={values.max()}"
            )

    if "mmsi" in df.columns:
        print(f"Unique MMSIs: {df['mmsi'].nunique(dropna=True):,}")

    if {"cell_ll_lat", "cell_ll_long"} <= set(df.columns):
        lat = pd.to_numeric(df["cell_ll_lat"], errors="coerce")
        lon = pd.to_numeric(df["cell_ll_long"], errors="coerce")

        coords = pd.DataFrame({"lat": lat, "lon": lon}).dropna().drop_duplicates()
        print(f"Unique coordinate pairs: {len(coords):,}")

        lat_steps = np.sort(coords["lat"].unique())
        lon_steps = np.sort(coords["lon"].unique())

        if len(lat_steps) > 1:
            lat_diffs = np.diff(lat_steps)
            lat_diffs = lat_diffs[lat_diffs > 1e-12]
            if len(lat_diffs):
                print(
                    "Latitude grid step(s), smallest observed: "
                    f"{lat_diffs.min():.10g}"
                )

        if len(lon_steps) > 1:
            lon_diffs = np.diff(lon_steps)
            lon_diffs = lon_diffs[lon_diffs > 1e-12]
            if len(lon_diffs):
                print(
                    "Longitude grid step(s), smallest observed: "
                    f"{lon_diffs.min():.10g}"
                )

    # Basic data-quality checks
    if "hours" in df.columns and "fishing_hours" in df.columns:
        hours = pd.to_numeric(df["hours"], errors="coerce")
        fishing = pd.to_numeric(df["fishing_hours"], errors="coerce")

        print(f"Negative hours: {(hours < 0).sum():,}")
        print(f"Negative fishing_hours: {(fishing < 0).sum():,}")
        print(
            "Rows where fishing_hours > hours: "
            f"{(fishing > hours).sum():,}"
        )

    print(f"Exact duplicate rows: {df.duplicated().sum():,}")

    return df


def main():
    if not DATA_ROOT.exists():
        print(f"DATA_ROOT does not exist: {DATA_ROOT.resolve()}")
        print("Edit DATA_ROOT at the top of this script.")
        return

    files = sorted(DATA_ROOT.glob("*/*.csv"))

    if not files:
        print(f"No CSV files found below: {DATA_ROOT.resolve()}")
        return

    print(f"Found {len(files)} CSV files.")

    summary = []

    for path in files:
        df = profile_file(path)

        if df is None:
            continue

        summary.append(
            {
                "file": str(path),
                "rows": len(df),
                "columns": len(df.columns),
            }
        )

    print("\n" + "=" * 80)
    print("FILE SUMMARY")
    print("=" * 80)

    summary_df = pd.DataFrame(summary)
    print(summary_df.to_string(index=False))

    out = Path("ais_file_summary.csv")
    summary_df.to_csv(out, index=False)
    print(f"\nSaved summary to: {out.resolve()}")


if __name__ == "__main__":
    main()