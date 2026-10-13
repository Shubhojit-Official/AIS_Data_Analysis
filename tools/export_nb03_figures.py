"""Export high-res figures from Notebook 03 logic (no notebook execution needed)."""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import linregress, spearmanr

BASE_DIR = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = BASE_DIR / "outputs" / "analysis"
PROCESSED_DIR = BASE_DIR / "outputs" / "processed"
FIG_DIR = BASE_DIR / "outputs" / "figures" / "nb03"
FIG_DIR.mkdir(parents=True, exist_ok=True)

MONTHLY_CELL_PATH = ANALYSIS_DIR / "monthly_cell.parquet"
AIS_PATH = PROCESSED_DIR / "ais_cleaned.parquet"

TREND_START_YEAR = 2015
TREND_END_YEAR = 2024
MIN_MONTHS_PER_YEAR = 3
MIN_YEARS = 5
ALPHA = 0.05
TOP_N = 6
DPI = 200


def cell_tag(lat, lon):
    return f"{lat:.1f}_{lon:.1f}".replace(".", "p").replace("-", "m")


def calculate_trend(group, value_col):
    g = group.sort_values("year")
    if g["year"].nunique() < MIN_YEARS:
        return pd.Series({
            "n_years": int(g["year"].nunique()),
            "slope_hours_per_year": np.nan, "intercept": np.nan,
            "r_squared": np.nan, "regression_p_value": np.nan,
            "spearman_rho": np.nan, "spearman_p_value": np.nan,
            "first_year": np.nan, "last_year": np.nan,
            "first_effort": np.nan, "last_effort": np.nan,
            "absolute_change_hours": np.nan, "percent_change": np.nan,
        })
    x = g["year"].to_numpy(dtype=float)
    y = g[value_col].to_numpy(dtype=float)
    if np.all(~np.isnan(y)) and np.nanstd(y) == 0:
        return pd.Series({
            "n_years": int(len(g)), "slope_hours_per_year": 0.0,
            "intercept": float(np.nanmean(y)), "r_squared": 0.0,
            "regression_p_value": np.nan, "spearman_rho": np.nan,
            "spearman_p_value": np.nan, "first_year": int(g["year"].iloc[0]),
            "last_year": int(g["year"].iloc[-1]), "first_effort": float(y[0]),
            "last_effort": float(y[-1]), "absolute_change_hours": 0.0,
            "percent_change": 0.0,
        })
    lr = linregress(x, y)
    rho, rho_p = spearmanr(x, y)
    first_effort, last_effort = y[0], y[-1]
    pct = (last_effort - first_effort) / first_effort * 100 if first_effort != 0 else np.nan
    return pd.Series({
        "n_years": int(len(g)), "slope_hours_per_year": lr.slope,
        "intercept": lr.intercept, "r_squared": lr.rvalue ** 2,
        "regression_p_value": lr.pvalue, "spearman_rho": rho,
        "spearman_p_value": rho_p, "first_year": int(g["year"].iloc[0]),
        "last_year": int(g["year"].iloc[-1]), "first_effort": first_effort,
        "last_effort": last_effort, "absolute_change_hours": last_effort - first_effort,
        "percent_change": pct,
    })


def main():
    monthly_cell = pd.read_parquet(MONTHLY_CELL_PATH)
    trend_monthly = monthly_cell[
        monthly_cell["year"].between(TREND_START_YEAR, TREND_END_YEAR)
    ].copy()

    # --- annual cell (nb03 section 4) ---
    annual_cell = (
        trend_monthly
        .groupby(["year", "cell_ll_lat", "cell_ll_lon"], as_index=False)
        .agg(
            fishing_hours=("fishing_hours", "sum"),
            total_hours=("total_hours", "sum"),
            vessel_months=("active_vessels", "sum"),
            active_days=("active_days", "sum"),
            months_available=("month", "nunique"),
        )
    )
    annual_cell["annual_coverage_pct"] = annual_cell["months_available"] / 12 * 100
    if AIS_PATH.exists():
        uniq = pd.read_parquet(
            AIS_PATH, columns=["year", "cell_ll_lat", "cell_ll_lon", "mmsi"]
        )
        uniq = uniq[uniq["year"].between(TREND_START_YEAR, TREND_END_YEAR)]
        true_uniques = (
            uniq.groupby(["year", "cell_ll_lat", "cell_ll_lon"], as_index=False)
            .agg(active_vessels_unique=("mmsi", "nunique"))
        )
        annual_cell = annual_cell.merge(
            true_uniques, on=["year", "cell_ll_lat", "cell_ll_lon"], how="left"
        )
    else:
        annual_cell["active_vessels_unique"] = np.nan

    annual_cell_valid = annual_cell[
        annual_cell["months_available"] >= MIN_MONTHS_PER_YEAR
    ].copy()
    annual_cell_valid["mean_monthly_fishing_hours"] = (
        annual_cell_valid["fishing_hours"] / annual_cell_valid["months_available"]
    )

    # --- global yearly (nb03 section 5) ---
    global_yearly = (
        trend_monthly.groupby("year", as_index=False)
        .agg(fishing_hours=("fishing_hours", "sum"), total_hours=("total_hours", "sum"))
    )
    cells_per_year = (
        trend_monthly.drop_duplicates(subset=["year", "cell_ll_lat", "cell_ll_lon"])
        .groupby("year").size().rename("cells_observed").reset_index()
    )
    global_yearly = global_yearly.merge(cells_per_year, on="year", how="left")

    # --- trends (nb03 sections 7-8) ---
    value_col = "mean_monthly_fishing_hours"
    cell_trends = (
        annual_cell_valid
        .groupby(["cell_ll_lat", "cell_ll_lon"], group_keys=False)
        .apply(lambda g: calculate_trend(g, value_col), include_groups=False)
        .reset_index()
    )
    conditions = [
        cell_trends["n_years"].lt(MIN_YEARS),
        cell_trends["regression_p_value"].lt(ALPHA) & cell_trends["slope_hours_per_year"].lt(0),
        cell_trends["regression_p_value"].lt(ALPHA) & cell_trends["slope_hours_per_year"].gt(0),
    ]
    cell_trends["trend_class"] = np.select(
        conditions, ["Insufficient data", "Declining", "Increasing"],
        default="Stable / not significant",
    )
    declining = (
        cell_trends[cell_trends["trend_class"] == "Declining"]
        .sort_values("slope_hours_per_year").copy()
    )

    saved = []

    # Fig 1: global
    plt.figure(figsize=(10, 5))
    plt.plot(global_yearly["year"], global_yearly["fishing_hours"], marker="o")
    plt.xlabel("Year")
    plt.ylabel("Fishing hours")
    plt.title("Total observed fishing effort by year")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    p = FIG_DIR / "01_global_fishing_effort_2015_2024.png"
    plt.savefig(p, dpi=DPI, bbox_inches="tight")
    plt.close()
    saved.append(p)

    # Figs 2-7: top declining cells
    for i, (lat, lon) in enumerate(
        declining.head(TOP_N)[["cell_ll_lat", "cell_ll_lon"]].itertuples(index=False, name=None),
        start=2,
    ):
        g = annual_cell_valid[
            (annual_cell_valid["cell_ll_lat"] == lat)
            & (annual_cell_valid["cell_ll_lon"] == lon)
        ].sort_values("year")
        plt.figure(figsize=(8, 4))
        plt.plot(g["year"], g["mean_monthly_fishing_hours"], marker="o")
        plt.xlabel("Year")
        plt.ylabel("Mean monthly fishing hours")
        plt.title(f"Cell ({lat:.1f}, {lon:.1f}) \u2014 annual fishing effort")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        p = FIG_DIR / f"{i:02d}_cell_{cell_tag(lat, lon)}_annual_effort.png"
        plt.savefig(p, dpi=DPI, bbox_inches="tight")
        plt.close()
        saved.append(p)

    # Fig 8: spatial pattern
    palette = {
        "Declining": "#d73027", "Increasing": "#1a9850",
        "Stable / not significant": "#969696", "Insufficient data": "#d9d9d9",
    }
    plot_df = cell_trends.copy()
    plot_df["color"] = plot_df["trend_class"].map(palette)
    plt.figure(figsize=(12, 7))
    for cls, grp in plot_df.groupby("trend_class"):
        plt.scatter(grp["cell_ll_lon"], grp["cell_ll_lat"], s=10, alpha=0.7,
                    c=grp["color"], label=f"{cls} (n={len(grp)})")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Spatial pattern of fishing-effort trends, 2015\u20132024 (mean monthly effort)")
    plt.grid(alpha=0.2)
    plt.legend(frameon=True, fontsize=9, loc="best")
    plt.tight_layout()
    p = FIG_DIR / "08_spatial_pattern_trends_2015_2024.png"
    plt.savefig(p, dpi=DPI, bbox_inches="tight")
    plt.close()
    saved.append(p)

    # Fig 9: magnitude of declining
    decline_map = cell_trends[cell_trends["trend_class"] == "Declining"].copy()
    plt.figure(figsize=(12, 7))
    sc = plt.scatter(decline_map["cell_ll_lon"], decline_map["cell_ll_lat"],
                     c=decline_map["slope_hours_per_year"], s=12, alpha=0.8)
    plt.colorbar(sc, label="Slope: mean monthly fishing hours/year")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Magnitude of declining fishing-effort trends")
    plt.grid(alpha=0.2)
    plt.tight_layout()
    p = FIG_DIR / "09_magnitude_declining_trends.png"
    plt.savefig(p, dpi=DPI, bbox_inches="tight")
    plt.close()
    saved.append(p)

    log = FIG_DIR / "_export_log.txt"
    with open(log, "w", encoding="utf-8") as f:
        f.write(f"Declining cells: {len(declining)}\n")
        f.write(declining[["cell_ll_lat", "cell_ll_lon", "n_years",
                           "slope_hours_per_year", "regression_p_value",
                           "percent_change"]].to_string(index=False))
        f.write("\n\nSaved:\n")
        for s in saved:
            f.write(f"{s.name}\n")
    print(f"Declining cells: {len(declining)}")
    print(f"Saved {len(saved)} figures to {FIG_DIR.resolve()}")


if __name__ == "__main__":
    main()
