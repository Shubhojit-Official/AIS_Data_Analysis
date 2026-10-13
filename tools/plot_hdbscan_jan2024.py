"""HDBSCAN clustering of January 2024 monthly cells, plotted on India coastline."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
import hdbscan

BASE_DIR = Path(__file__).resolve().parents[1]
FIG_DIR = BASE_DIR / "outputs" / "figures" / "nb04"
FIG_DIR.mkdir(parents=True, exist_ok=True)

MONTHLY = BASE_DIR / "outputs" / "analysis" / "monthly_cell.parquet"
GEO = BASE_DIR / "outputs" / "geo" / "ne_110m_admin_0_countries.geojson"

YEAR, MONTH = 2024, 1
MCS = 20  # mcs=10 fragments into 26 clusters; 20 gives ~5 clean coastal groups

m = pd.read_parquet(MONTHLY)
j = m[(m["year"] == YEAR) & (m["month"] == MONTH)].copy()
print(f"jan {YEAR}-{MONTH:02d} rows (all): {len(j)}")

# India window for clustering + map (drops far outliers like lon 122 / lat -11)
j = j[j["cell_ll_lon"].between(65, 95) & j["cell_ll_lat"].between(0, 28)].copy()
print(f"in India window: {len(j)}")

mean_lat = float(j["cell_ll_lat"].mean())
kx = float(np.cos(np.radians(mean_lat)) * 111.32)
X = np.column_stack([j["cell_ll_lon"].to_numpy() * kx,
                     j["cell_ll_lat"].to_numpy() * 110.57])

for mcs in [5, 10, 20]:
    lab = hdbscan.HDBSCAN(min_cluster_size=mcs).fit_predict(X)
    n_cl = len(set(lab)) - (1 if -1 in lab else 0)
    print(f"sweep mcs={mcs}: clusters={n_cl} noise={int((lab == -1).sum())}")

lab = hdbscan.HDBSCAN(min_cluster_size=MCS).fit_predict(X)
j["hdbscan_cluster"] = lab
n_cl = len(set(lab)) - (1 if -1 in lab else 0)
n_noise = int((lab == -1).sum())
print(f"chosen mcs={MCS}: clusters={n_cl} noise={n_noise}")

gj = json.load(open(GEO, encoding="utf-8"))
WANT = {"India", "Pakistan", "Bangladesh", "Myanmar", "Sri Lanka", "Nepal", "Bhutan"}
coast = []
for f in gj["features"]:
    nm = f["properties"].get("ADMIN") or f["properties"].get("NAME")
    if nm in WANT:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            coast.append(Polygon(poly[0], closed=True))

sizes = 6 + 90 * np.sqrt(j["fishing_hours"].to_numpy() / j["fishing_hours"].max())

fig, ax = plt.subplots(figsize=(10, 10))
ax.add_collection(PatchCollection(coast, facecolor="#e8e8e8", edgecolor="#555555",
                                  linewidths=0.6, zorder=1))
uniq = sorted(set(lab))
cmap = plt.get_cmap("tab20", max(len(uniq), 2))
for k in uniq:
    mk = lab == k
    ax.scatter(j.loc[mk, "cell_ll_lon"], j.loc[mk, "cell_ll_lat"],
               s=sizes[mk], alpha=0.8,
               color="#bdbdbd" if k == -1 else cmap(k % 20),
               label=f"noise" if k == -1 else f"cluster {k} (n={int(mk.sum())})",
               zorder=3)
ax.set_xlim(65, 95)
ax.set_ylim(0, 28)
ax.set_aspect("equal", adjustable="box")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title(f"HDBSCAN clustering — January {YEAR} monthly cells on India map\n"
             f"(min_cluster_size={MCS}, clusters={n_cl}, noise={n_noise}; size = fishing_hours)")
ax.grid(alpha=0.2)
ax.legend(fontsize=7, loc="best", frameon=True, markerscale=1.5)
fig.tight_layout()
out = FIG_DIR / f"nb04_hdbscan_jan{YEAR}_india_map.png"
fig.savefig(out, dpi=200, bbox_inches="tight")
print("saved:", out.resolve())

j.to_parquet(BASE_DIR / "outputs" / "analysis" / f"hdbscan_jan{YEAR}_clusters.parquet", index=False)
print("saved cluster table")
