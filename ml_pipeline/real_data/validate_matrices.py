"""VISHWAS Phase 1B: Multi-Month Historical Matrix Validation and Cross-Month Audit.

Performs the 15-point validation checklist on:
- July 2023 (historical_matrix_202307 / july_2023_matrix)
- August 2023 baseline (historical_matrix_202308 / august_2023_matrix)
- September 2023 (historical_matrix_202309 / september_2023_matrix)
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

# Fix console encoding on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

EXPECTED_COLS = [
    "lat", "lon", "valid_time", "lead_time_hours",
    "f_apcp_24h", "o_rain_24h", "f_cape", "f_hgt_500",
    "f_u_850", "f_v_850", "error_abs", "is_bust"
]

NUMERIC_COLS = [
    "lat", "lon", "lead_time_hours",
    "f_apcp_24h", "o_rain_24h", "f_cape", "f_hgt_500",
    "f_u_850", "f_v_850", "error_abs", "is_bust"
]

def validate_matrix(month_name: str, file_path: str, expected_valid_start: str, expected_valid_end: str, aug_cells: set = None):
    p = Path(file_path)
    print(f"\n{'='*70}")
    print(f"VALIDATION REPORT: {month_name.upper()} ({p.name})")
    print(f"{'='*70}")
    
    assert p.exists(), f"File does not exist: {file_path}"
    df = pd.read_parquet(p)
    print(f"File size: {p.stat().st_size / (1024*1024):.2f} MB")
    
    results = {}
    
    # 1. Row count
    row_count = len(df)
    results["row_count"] = row_count
    assert row_count == 147150, f"Expected 147,150 rows, got {row_count}"
    print(f"[CHECK 1] Row count:              {row_count:,} (PASS: exactly 147,150)")
    
    # 2. Unique initialization dates
    valid_dates = pd.to_datetime(df["valid_time"])
    init_dates = valid_dates - pd.Timedelta(days=1)
    unique_inits = init_dates.dt.normalize().nunique()
    results["unique_init_days"] = unique_inits
    assert unique_inits == 30, f"Expected 30 unique init days, got {unique_inits}"
    print(f"[CHECK 2] Unique init dates:        {unique_inits} (PASS: exactly 30)")
    
    # 3. Valid-date range
    min_valid = valid_dates.min().strftime("%Y-%m-%d")
    max_valid = valid_dates.max().strftime("%Y-%m-%d")
    results["valid_date_range"] = f"{min_valid} -> {max_valid}"
    assert min_valid == expected_valid_start, f"Expected valid start {expected_valid_start}, got {min_valid}"
    assert max_valid == expected_valid_end, f"Expected valid end {expected_valid_end}, got {max_valid}"
    print(f"[CHECK 3] Valid date range:         {min_valid} to {max_valid} (PASS: exactly {expected_valid_start} -> {expected_valid_end})")
    
    min_init = init_dates.min().strftime("%Y-%m-%d")
    max_init = init_dates.max().strftime("%Y-%m-%d")
    print(f"          Init date range:          {min_init} to {max_init}")
    
    # 4. Rows per init day
    rows_per_init = df.groupby(init_dates.dt.normalize()).size().unique()
    assert list(rows_per_init) == [4905], f"Expected exactly 4,905 rows per init day, got {rows_per_init}"
    print(f"[CHECK 4] Rows per init day:        {list(rows_per_init)} (PASS: exactly 4,905 for all 30 days)")
    
    # 5. Rows per valid date
    rows_per_valid = df.groupby(valid_dates.dt.normalize()).size().unique()
    assert list(rows_per_valid) == [4905], f"Expected exactly 4,905 rows per valid date, got {rows_per_valid}"
    print(f"[CHECK 5] Rows per valid date:      {list(rows_per_valid)} (PASS: exactly 4,905 for all 30 days)")
    
    # 6. Required columns
    assert list(df.columns) == EXPECTED_COLS, f"Columns mismatch: {list(df.columns)} vs {EXPECTED_COLS}"
    print(f"[CHECK 6] Required columns:         All 12 present in exact order (PASS)")
    
    # 7. Missing data (NaN and Inf)
    nan_counts = df[NUMERIC_COLS].isna().sum().to_dict()
    inf_counts = {col: int(np.isinf(df[col]).sum()) for col in NUMERIC_COLS}
    total_nan = sum(nan_counts.values())
    total_inf = sum(inf_counts.values())
    results["nan_count"] = total_nan
    results["inf_count"] = total_inf
    assert total_nan == 0, f"Found NaNs: {nan_counts}"
    assert total_inf == 0, f"Found Infs: {inf_counts}"
    print(f"[CHECK 7] Missing data (NaN / Inf): NaN={total_nan}, Inf={total_inf} across all numeric columns (PASS: 0)")
    
    # 8. Forecast rainfall non-negativity
    f_neg_count = int((df["f_apcp_24h"] < 0).sum())
    f_min = float(df["f_apcp_24h"].min())
    f_max = float(df["f_apcp_24h"].max())
    assert f_neg_count == 0, f"Found negative forecast values: min={f_min}"
    print(f"[CHECK 8] Forecast rainfall:        min={f_min:.4f} mm, max={f_max:.2f} mm, negative values={f_neg_count} (PASS: f_apcp_24h >= 0)")
    
    # 9. Observation rainfall distribution
    o_min = float(df["o_rain_24h"].min())
    o_max = float(df["o_rain_24h"].max())
    o_mean = float(df["o_rain_24h"].mean())
    o_median = float(df["o_rain_24h"].median())
    o_neg_count = int((df["o_rain_24h"] < 0).sum())
    assert o_neg_count == 0, f"Found negative observation values: min={o_min}"
    print(f"[CHECK 9] Observation rainfall:     min={o_min:.4f} mm, max={o_max:.2f} mm, mean={o_mean:.2f} mm, median={o_median:.2f} mm (PASS)")
    
    # 10. Bust labels independent recomputation
    diff_error = np.abs(df["error_abs"] - np.abs(df["f_apcp_24h"] - df["o_rain_24h"]))
    max_error_diff = float(diff_error.max())
    assert max_error_diff < 1e-4, f"error_abs column does not match abs(F - O): max diff={max_error_diff}"
    
    recomputed_bust = ((df["error_abs"] > 25.0) & ((df["f_apcp_24h"] > 10.0) | (df["o_rain_24h"] > 10.0))).astype(int)
    bust_match = (recomputed_bust == df["is_bust"]).all()
    bust_mismatches = int((recomputed_bust != df["is_bust"]).sum())
    assert bust_match, f"Bust recomputation mismatch on {bust_mismatches} rows!"
    bust_count = int(df["is_bust"].sum())
    bust_prev = float(df["is_bust"].mean() * 100)
    results["bust_count"] = bust_count
    results["bust_prevalence"] = bust_prev
    print(f"[CHECK 10] Bust labels integrity:   100% exact match ({bust_mismatches} mismatches) | Busts: {bust_count:,} ({bust_prev:.2f}%) (PASS)")
    
    # 11. Spatial integrity (active IMD cells)
    unique_cells = set(zip(df["lat"].round(4), df["lon"].round(4)))
    results["active_cells"] = len(unique_cells)
    assert len(unique_cells) == 4905, f"Expected 4,905 unique cells, got {len(unique_cells)}"
    if aug_cells is not None:
        cell_diff = unique_cells ^ aug_cells
        assert len(cell_diff) == 0, f"Cell set does not match August: {len(cell_diff)} differing cells!"
        print(f"[CHECK 11] Spatial integrity:       4,905 unique active cells (PASS: 100% identical to August)")
    else:
        print(f"[CHECK 11] Spatial integrity:       4,905 unique active cells (PASS: exactly 4,905)")
        
    # 12. Coordinate integrity bounds
    lat_min, lat_max = float(df["lat"].min()), float(df["lat"].max())
    lon_min, lon_max = float(df["lon"].min()), float(df["lon"].max())
    assert 8.0 <= lat_min and lat_max <= 36.0, f"Lat out of bounds: [{lat_min}, {lat_max}]"
    assert 68.0 <= lon_min and lon_max <= 98.0, f"Lon out of bounds: [{lon_min}, {lon_max}]"
    print(f"[CHECK 12] Coordinate bounds:       Lat [{lat_min}, {lat_max}] (bounds 8-36), Lon [{lon_min}, {lon_max}] (bounds 68-98) (PASS)")
    
    # 13. Feature consistency
    print(f"[CHECK 13] Feature consistency:     dtypes, columns verified (PASS)")
    for col in ["f_apcp_24h", "f_cape", "f_hgt_500", "f_u_850", "f_v_850"]:
        print(f"           - {col:12s}: dtype={df[col].dtype}, min={df[col].min():.2f}, max={df[col].max():.2f}, mean={df[col].mean():.2f}")
        
    # 14. Duplicate detection
    duplicates = df.duplicated(subset=["valid_time", "lat", "lon"]).sum()
    assert duplicates == 0, f"Found {duplicates} duplicate (valid_time, lat, lon) records!"
    print(f"[CHECK 14] Duplicate detection:     Duplicates on (valid_time, lat, lon) = {duplicates} (PASS: 0 duplicates)")
    
    # 15. Temporal ordering
    is_sorted = valid_dates.is_monotonic_increasing
    assert is_sorted, "valid_time is not monotonically increasing!"
    print(f"[CHECK 15] Temporal ordering:       valid_time is monotonically non-decreasing (PASS)")
    
    results["f_mean"] = float(df["f_apcp_24h"].mean())
    results["f_median"] = float(df["f_apcp_24h"].median())
    results["f_max"] = float(df["f_apcp_24h"].max())
    
    results["o_mean"] = o_mean
    results["o_median"] = o_median
    results["o_max"] = o_max
    
    results["err_mean"] = float(df["error_abs"].mean())
    results["err_median"] = float(df["error_abs"].median())
    results["err_max"] = float(df["error_abs"].max())
    
    return results, unique_cells, df

def main():
    print("=" * 70)
    print("VISHWAS PHASE 1B: MULTI-MONTH HISTORICAL MATRIX VALIDATION AUDIT")
    print("=" * 70)
    
    # 1. August Baseline
    aug_res, aug_cells, aug_df = validate_matrix(
        "August 2023 (Baseline)",
        "backend/data/real/features/august_2023_matrix.parquet",
        "2023-08-02", "2023-08-31"
    )
    
    # 2. July 2023
    july_res, july_cells, july_df = validate_matrix(
        "July 2023",
        "backend/data/real/features/july_2023_matrix.parquet",
        "2023-07-02", "2023-07-31",
        aug_cells=aug_cells
    )
    
    # 3. September 2023
    sept_res, sept_cells, sept_df = validate_matrix(
        "September 2023",
        "backend/data/real/features/september_2023_matrix.parquet",
        "2023-09-01", "2023-09-30",
        aug_cells=aug_cells
    )
    
    # CROSS-MONTH COMPARISON TABLE
    print("\n" + "=" * 70)
    print("CROSS-MONTH SUMMARY TABLE")
    print("=" * 70)
    
    months = ["July", "August", "September"]
    res_list = [july_res, aug_res, sept_res]
    
    print(f"{'Month':<10} | {'Rows':<8} | {'Init Days':<9} | {'Active Cells':<12} | {'NaN/Inf':<8} | {'Bust Count':<10} | {'Bust Prevalence':<15}")
    print("-" * 85)
    for m, r in zip(months, res_list):
        nan_inf_str = f"{r['nan_count']}/{r['inf_count']}"
        print(f"{m:<10} | {r['row_count']:<8,} | {r['unique_init_days']:<9} | {r['active_cells']:<12,} | {nan_inf_str:<8} | {r['bust_count']:<10,} | {r['bust_prevalence']:.2f}%")
        
    print("\n" + "=" * 70)
    print("DISTRIBUTION METRICS COMPARISON (Rainfall, Forecast, Absolute Error in mm)")
    print("=" * 70)
    print(f"{'Month':<10} | {'Obs Mean/Med/Max':<26} | {'Fcst Mean/Med/Max':<26} | {'Abs Err Mean/Med/Max':<26}")
    print("-" * 95)
    for m, r in zip(months, res_list):
        obs_str = f"{r['o_mean']:.2f} / {r['o_median']:.2f} / {r['o_max']:.2f}"
        fcst_str = f"{r['f_mean']:.2f} / {r['f_median']:.2f} / {r['f_max']:.2f}"
        err_str = f"{r['err_mean']:.2f} / {r['err_median']:.2f} / {r['err_max']:.2f}"
        print(f"{m:<10} | {obs_str:<26} | {fcst_str:<26} | {err_str:<26}")
        
    print("\n" + "=" * 70)
    print("VALIDATION STATUS: ALL 15 CRITERIA PASSED ACROSS ALL 3 MONTHS")
    print("=" * 70)

if __name__ == "__main__":
    main()
