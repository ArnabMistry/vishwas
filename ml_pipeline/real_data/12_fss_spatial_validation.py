"""VISHWAS Phase 2B: Real-Data Fractions Skill Score (FSS) Spatial Verification (Track B).

Scientific Scope:
- Objective: Spatially verify raw GFS 24h precipitation against IMD observations for D1–D9.
- Domain: 0.25° grid, 4,905 active IMD land cells (Indian domain).
- Population: Retrospective spatial verification population across all 90 cohort days (July, August, September 2023).
- Verification fields: raw GFS forecast (f_apcp_24h) vs IMD observation (o_rain_24h).
- Thresholds: exactly 1 mm, 10 mm, 25 mm per 24h.
- Neighborhood scales: square grid windows: 1×1, 3×3, 5×5, 7×7.
- Active land mask: Numerator is active land exceedances; denominator is active land cells in neighborhood.
- Metrics computed:
  1. Pooled FSS and case-level median FSS.
  2. Frequency bias by lead and threshold.
  3. FSS-0.5 reference horizons (largest lead in D1–D9 with pooled FSS >= 0.50).
  4. Scale and threshold sensitivity analysis.

Outputs:
- ml_pipeline/real_data/phase2b_fss_metrics.json
"""

import sys
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.signal import convolve2d

# Configure console output for Windows UTF-8 safety
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

THRESHOLDS = [1.0, 10.0, 25.0]
SCALES = [1, 3, 5, 7]  # Window sizes WxW
SCALE_LABELS = {1: "1x1", 3: "3x3", 5: "5x5", 7: "7x7"}


def load_spatial_verification_data(features_dir: Path) -> dict:
    """Load D1 and D2–D9 datasets and assemble case records by lead."""
    print("Loading retrospective spatial verification population...")
    cases_by_lead = {l: [] for l in range(1, 10)}

    for m in ["july", "august", "september"]:
        # 1. D1 dataset
        d1_path = features_dir / f"{m}_2023_matrix.parquet"
        assert d1_path.exists(), f"Missing D1 matrix: {d1_path}"
        df_d1 = pd.read_parquet(str(d1_path))
        df_d1["valid_time"] = pd.to_datetime(df_d1["valid_time"])
        df_d1["init_time"] = df_d1["valid_time"] - pd.Timedelta(days=1)
        df_d1["lead_day"] = 1

        for dt, group in df_d1.groupby("init_time"):
            assert len(group) == 4905, f"Unexpected cell count for D1 {dt}: {len(group)}"
            group_sorted = group.sort_values(["lat", "lon"]).reset_index(drop=True)
            cases_by_lead[1].append({
                "init_time": dt.strftime("%Y-%m-%d"),
                "f_apcp": group_sorted["f_apcp_24h"].values,
                "o_rain": group_sorted["o_rain_24h"].values,
                "coords": group_sorted[["lat", "lon"]].values,
            })

        # 2. D2–D9 dataset
        d2_d9_path = features_dir / f"{m}_2023_d2_d9.parquet"
        assert d2_d9_path.exists(), f"Missing D2-D9 matrix: {d2_d9_path}"
        df_d2_d9 = pd.read_parquet(str(d2_d9_path))
        df_d2_d9["init_time"] = pd.to_datetime(df_d2_d9["init_time"])

        for lead in range(2, 10):
            df_lead = df_d2_d9[df_d2_d9["lead_day"] == lead]
            for dt, group in df_lead.groupby("init_time"):
                assert len(group) == 4905, f"Unexpected cell count for D{lead} {dt}: {len(group)}"
                group_sorted = group.sort_values(["lat", "lon"]).reset_index(drop=True)
                cases_by_lead[lead].append({
                    "init_time": dt.strftime("%Y-%m-%d"),
                    "f_apcp": group_sorted["f_apcp_24h"].values,
                    "o_rain": group_sorted["o_rain_24h"].values,
                    "coords": group_sorted[["lat", "lon"]].values,
                })

    for lead in range(1, 10):
        print(f"  Lead D{lead}: {len(cases_by_lead[lead])} retrospective spatial verification cases.")
        assert len(cases_by_lead[lead]) == 90, f"Expected 90 cases for D{lead}, got {len(cases_by_lead[lead])}"

    return cases_by_lead


def build_grid_indexer(ref_coords: pd.DataFrame):
    """Establish mapping between 4,905 active land cells and 2D regular grid."""
    coords_sorted = ref_coords.sort_values(["lat", "lon"]).reset_index(drop=True)
    lats = np.arange(8.25, 36.25, 0.25)
    lons = np.arange(68.0, 97.5, 0.25)

    lat_map = {round(float(l), 2): i for i, l in enumerate(lats)}
    lon_map = {round(float(l), 2): i for i, l in enumerate(lons)}

    i_lats = np.array([lat_map[round(float(lat), 2)] for lat in coords_sorted["lat"]])
    i_lons = np.array([lon_map[round(float(lon), 2)] for lon in coords_sorted["lon"]])

    grid_shape = (len(lats), len(lons))
    active_mask = np.zeros(grid_shape, dtype=bool)
    active_mask[i_lats, i_lons] = True

    assert active_mask.sum() == 4905, f"Mask active count mismatch: {active_mask.sum()}"

    # Precompute neighborhood denominator grids D for each scale W
    denominators = {}
    for W in SCALES:
        kernel = np.ones((W, W), dtype=np.float64)
        # Sum of active land cells in neighborhood
        D = convolve2d(active_mask.astype(np.float64), kernel, mode="same", boundary="fill", fillvalue=0)
        # For active cells, D must be >= 1
        active_D = D[active_mask]
        assert np.all(active_D >= 1.0), "Found active cell with 0 active neighbors"
        denominators[W] = D

    return {
        "grid_shape": grid_shape,
        "i_lats": i_lats,
        "i_lons": i_lons,
        "active_mask": active_mask,
        "denominators": denominators,
    }


def compute_fss_suite(cases_by_lead: dict, grid_info: dict) -> dict:
    """Compute Fractions Skill Score and Frequency Bias across leads, thresholds, and scales."""
    grid_shape = grid_info["grid_shape"]
    i_lats = grid_info["i_lats"]
    i_lons = grid_info["i_lons"]
    active_mask = grid_info["active_mask"]
    denominators = grid_info["denominators"]

    table_d_fss = []
    table_e_bias = []
    full_metrics = {}

    for lead in range(1, 10):
        lead_cases = cases_by_lead[lead]
        lead_key = f"d{lead}"
        full_metrics[lead_key] = {"thresholds": {}}

        for thresh in THRESHOLDS:
            thresh_key = f"{int(thresh)}mm"
            full_metrics[lead_key]["thresholds"][thresh_key] = {"scales": {}}

            # Frequency Bias tracking across all active cells
            total_f_hits = 0
            total_o_hits = 0
            total_opportunities = len(lead_cases) * 4905

            # Accumulators for each scale
            scale_mse_f = {W: [] for W in SCALES}
            scale_mse_ref = {W: [] for W in SCALES}
            scale_case_fss = {W: [] for W in SCALES}

            for case in lead_cases:
                f_raw = case["f_apcp"]
                o_raw = case["o_rain"]

                f_binary = (f_raw >= thresh).astype(np.float64)
                o_binary = (o_raw >= thresh).astype(np.float64)

                total_f_hits += int(np.sum(f_binary))
                total_o_hits += int(np.sum(o_binary))

                # Project onto 2D regular grid
                F_grid = np.zeros(grid_shape, dtype=np.float64)
                O_grid = np.zeros(grid_shape, dtype=np.float64)
                F_grid[i_lats, i_lons] = f_binary
                O_grid[i_lats, i_lons] = o_binary

                for W in SCALES:
                    kernel = np.ones((W, W), dtype=np.float64)
                    D = denominators[W]

                    N_f = convolve2d(F_grid, kernel, mode="same", boundary="fill", fillvalue=0)
                    N_o = convolve2d(O_grid, kernel, mode="same", boundary="fill", fillvalue=0)

                    P_f = N_f[active_mask] / D[active_mask]
                    P_o = N_o[active_mask] / D[active_mask]

                    mse_f = float(np.mean((P_f - P_o) ** 2))
                    mse_ref = float(np.mean(P_f ** 2 + P_o ** 2))

                    scale_mse_f[W].append(mse_f)
                    scale_mse_ref[W].append(mse_ref)

                    if mse_ref > 1e-12:
                        fss_val = float(np.clip(1.0 - (mse_f / mse_ref), 0.0, 1.0))
                        scale_case_fss[W].append(fss_val)
                    else:
                        # Undefined when both forecast and observation have zero events in domain
                        pass

            # Frequency bias calculation for this lead × threshold
            f_freq = round(total_f_hits / total_opportunities, 4)
            o_freq = round(total_o_hits / total_opportunities, 4)
            freq_bias = round(f_freq / o_freq, 4) if o_freq > 0 else None

            table_e_bias.append({
                "lead": f"D{lead}",
                "threshold_mm": thresh,
                "forecast_frequency": f_freq,
                "obs_frequency": o_freq,
                "frequency_bias": freq_bias,
                "total_forecast_hits": total_f_hits,
                "total_obs_hits": total_o_hits,
            })

            full_metrics[lead_key]["thresholds"][thresh_key]["frequency_bias"] = {
                "forecast_frequency": f_freq,
                "obs_frequency": o_freq,
                "frequency_bias": freq_bias,
            }

            # FSS aggregation across scales
            for W in SCALES:
                w_label = SCALE_LABELS[W]
                sum_mse_f = float(np.sum(scale_mse_f[W]))
                sum_mse_ref = float(np.sum(scale_mse_ref[W]))
                valid_cases = len(scale_case_fss[W])

                if sum_mse_ref > 1e-12:
                    pooled_fss = round(float(np.clip(1.0 - (sum_mse_f / sum_mse_ref), 0.0, 1.0)), 4)
                else:
                    pooled_fss = None

                if valid_cases > 0:
                    med_fss = round(float(np.median(scale_case_fss[W])), 4)
                else:
                    med_fss = None

                table_d_fss.append({
                    "lead": f"D{lead}",
                    "threshold_mm": thresh,
                    "scale": w_label,
                    "valid_cases": valid_cases,
                    "pooled_fss": pooled_fss,
                    "median_case_fss": med_fss,
                })

                full_metrics[lead_key]["thresholds"][thresh_key]["scales"][w_label] = {
                    "valid_cases": valid_cases,
                    "pooled_fss": pooled_fss,
                    "median_case_fss": med_fss,
                }

    return {
        "table_d_fss": table_d_fss,
        "table_e_bias": table_e_bias,
        "full_metrics": full_metrics,
    }


def compute_fss_05_horizons(table_d_fss: list) -> list:
    """Find largest evaluated lead in D1–D9 whose pooled FSS is >= 0.50."""
    horizons = []
    for thresh in THRESHOLDS:
        for W in SCALES:
            w_label = SCALE_LABELS[W]
            rows = [
                r for r in table_d_fss
                if r["threshold_mm"] == thresh and r["scale"] == w_label
            ]
            rows_sorted = sorted(rows, key=lambda x: int(x["lead"][1:]))

            qualifying_leads = [
                int(r["lead"][1:]) for r in rows_sorted
                if r["pooled_fss"] is not None and r["pooled_fss"] >= 0.50
            ]

            if not qualifying_leads:
                ref_horizon = "none"
            elif len(qualifying_leads) == 9 and set(qualifying_leads) == set(range(1, 10)):
                ref_horizon = "beyond D9"
            else:
                max_lead = max(qualifying_leads)
                ref_horizon = f"D{max_lead}"

            horizons.append({
                "threshold_mm": thresh,
                "scale": w_label,
                "reference_horizon": ref_horizon,
            })
    return horizons


def build_compact_fss_profile(table_d_fss: list) -> list:
    """Construct Table G: Compact D1–D9 FSS profile across representative scales."""
    profile = []
    for lead in range(1, 10):
        lead_str = f"D{lead}"
        row = {"lead": lead_str}
        for thresh in [1.0, 10.0, 25.0]:
            t_int = int(thresh)
            for scale in ["1x1", "5x5"]:
                match = [
                    r for r in table_d_fss
                    if r["lead"] == lead_str and r["threshold_mm"] == thresh and r["scale"] == scale
                ]
                col_name = f"fss_{t_int}mm_{scale}"
                row[col_name] = match[0]["pooled_fss"] if match else None
        profile.append(row)
    return profile


def main():
    t0 = time.time()
    features_dir = Path("backend/data/real/features")
    metrics_out = Path("ml_pipeline/real_data/phase2b_fss_metrics.json")

    print("\n" + "=" * 75)
    print("VISHWAS PHASE 2B: FRACTIONS SKILL SCORE (FSS) SPATIAL VERIFICATION (TRACK B)")
    print("=" * 75)

    # 1. Load Data
    cases_by_lead = load_spatial_verification_data(features_dir)

    # 2. Build 2D Grid & Mask
    ref_coords_path = features_dir / "august_2023_matrix.parquet"
    ref_df = pd.read_parquet(str(ref_coords_path))[["lat", "lon"]].drop_duplicates()
    grid_info = build_grid_indexer(ref_df)

    # 3. Compute FSS Suite
    print("\n[1/3] Computing FSS and Frequency Bias across 810 spatial cases...")
    fss_res = compute_fss_suite(cases_by_lead, grid_info)
    table_d_fss = fss_res["table_d_fss"]
    table_e_bias = fss_res["table_e_bias"]
    full_metrics = fss_res["full_metrics"]

    # 4. FSS-0.5 Reference Horizons & Compact Profile
    print("\n[2/3] Computing FSS-0.5 Reference Horizons and Compact Profiles...")
    table_f_horizons = compute_fss_05_horizons(table_d_fss)
    table_g_profile = build_compact_fss_profile(table_d_fss)

    for h in table_f_horizons:
        print(f"      Threshold {h['threshold_mm']:>4.1f} mm | Scale {h['scale']:<3}: Horizon = {h['reference_horizon']}")

    # 5. Save JSON Package
    print("\n[3/3] Writing Structured FSS Metrics to JSON...")
    output_package = {
        "metadata": {
            "title": "VISHWAS Phase 2B: Fractions Skill Score (FSS) Spatial Verification (Track B)",
            "verification_population": "Retrospective spatial verification population (July, August, September 2023)",
            "total_cases_per_lead": 90,
            "total_spatial_cases": 810,
            "active_land_cells": 4905,
            "grid_resolution_deg": 0.25,
            "thresholds_mm_24h": THRESHOLDS,
            "neighborhood_scales": [SCALE_LABELS[w] for w in SCALES],
            "formula_reference": "Roberts and Lean (2008) spatial fractions skill score",
            "fss_05_reference_definition": (
                "FSS=0.5 is used here only as a descriptive reference threshold. "
                "Usefulness depends on threshold, scale, domain and forecast/observation characteristics. "
                "Do NOT extrapolate to D10."
            ),
            "d10_status": "UNAVAILABLE_EMPIRICALLY",
        },
        "table_d_fss": table_d_fss,
        "table_e_frequency_bias": table_e_bias,
        "table_f_fss_05_horizons": table_f_horizons,
        "table_g_compact_profile": table_g_profile,
        "full_metrics_by_lead": full_metrics,
    }

    with open(metrics_out, "w", encoding="utf-8") as f:
        json.dump(output_package, f, indent=2)

    elapsed = time.time() - t0
    print(f"\nFSS spatial verification finished in {elapsed:.1f}s. Saved to: {metrics_out}\n")


if __name__ == "__main__":
    main()
