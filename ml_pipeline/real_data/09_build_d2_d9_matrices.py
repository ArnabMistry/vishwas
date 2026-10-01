"""VISHWAS Phase 2A: Retrieve GFS Endpoints and Construct D2–D9 Historical Matrices.

Scope:
- Historical initialization cohorts:
  1. July 2023:      2023-07-01 to 2023-07-30 (30 days)
  2. August 2023:    2023-08-01 to 2023-08-30 (30 days)
  3. September 2023: 2023-08-31 to 2023-09-29 (30 days)
- Lead days evaluated: D2 through D9 (8 leads)
- Forecast horizons per init:
  +27h (already cached) and new: +51h, +75h, +99h, +123h, +147h, +171h, +195h, +219h (720 slices)
- 24h precipitation: max(APCP[24L+3] - APCP[24(L-1)+3], 0.0)
- Predictors at endpoint 24L+3: f_apcp_24h, f_cape, f_hgt_500, f_u_850, f_v_850, lat, lon
- IMD daily rainfall observation aligned to valid date = init date + L days
- Exact 4,905 active land cells matching August baseline
- Output: 3 Parquet files with 1,177,200 rows each (3,531,600 total instances).
"""

import sys
import time
import argparse
import threading
import concurrent.futures
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
from herbie import Herbie
import imdlib

# Reconfigure stdout/stderr for Windows console UTF-8 safety
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Required constants
COHORTS = [
    ("july", "2023-07-01", "2023-07-30"),
    ("august", "2023-08-01", "2023-08-30"),
    ("september", "2023-08-31", "2023-09-29"),
]

NEW_ENDPOINTS = [51, 75, 99, 123, 147, 171, 195, 219]
ALL_REQUIRED_ENDPOINTS = [27, 51, 75, 99, 123, 147, 171, 195, 219]

REQUIRED_VARS = ["apcp", "cape", "hgt_500", "u_850", "v_850"]
EXPECTED_CELLS_PER_SLICE = 4905
EXPECTED_ROWS_PER_MONTH = 30 * 8 * EXPECTED_CELLS_PER_SLICE  # 1,177,200

STANDARD_COLUMNS = [
    "init_time",
    "valid_time",
    "lead_day",
    "lat",
    "lon",
    "lead_time_hours",
    "f_apcp_24h",
    "o_rain_24h",
    "f_cape",
    "f_hgt_500",
    "f_u_850",
    "f_v_850",
    "error_abs",
    "is_bust",
]

# Lock for thread-safe ecCodes / cfgrib operations across threads
eccodes_lock = threading.Lock()


def is_valid_cached_slice(nc_path: Path, req_vars: list = REQUIRED_VARS) -> bool:
    """Verify local NetCDF slice exists, is non-zero, opens, and has required variables/coords."""
    if not nc_path.exists() or nc_path.stat().st_size == 0:
        return False
    try:
        with xr.open_dataset(nc_path) as ds:
            if not all(v in ds.data_vars for v in req_vars):
                return False
            if "latitude" not in ds.coords or "longitude" not in ds.coords:
                return False
            lat_min, lat_max = float(ds.latitude.min()), float(ds.latitude.max())
            lon_min, lon_max = float(ds.longitude.min()), float(ds.longitude.max())
            if lat_min > 8.5 or lat_max < 35.5 or lon_min > 68.5 or lon_max < 97.5:
                return False
            return True
    except Exception:
        return False


def fetch_and_save_slice(args) -> tuple:
    """Download and crop single GFS slice with retry logic and ecCodes synchronization."""
    init_str, fxx, raw_dir = args
    dt_compact = init_str[:10].replace("-", "")
    gfs_dir = Path(raw_dir) / "gfs"
    cached_nc = gfs_dir / f"gfs_{dt_compact}_f{fxx:02d}.nc"

    if is_valid_cached_slice(cached_nc):
        return (init_str, fxx, "cached", 0.0)

    acc_str = f"0-{fxx} hour acc fcst"
    search_expr = f":(?:APCP:surface:{acc_str}|CAPE:surface|HGT:500 mb|UGRD:850 mb|VGRD:850 mb):"

    t0 = time.time()
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            H = Herbie(init_str, model="gfs", fxx=fxx, save_dir=str(raw_dir), overwrite=True)

            # Parallel S3 byte-range download
            grib_file = H.download(search_expr)

            # ecCodes decoding under mutual exclusion lock
            with eccodes_lock:
                ds_list = H.xarray(search_expr, remove_grib=True)
                if isinstance(ds_list, xr.Dataset):
                    ds_list = [ds_list]

                merged = xr.Dataset()
                for ds in ds_list:
                    ds_crop = ds.sel(latitude=slice(36.0, 8.0), longitude=slice(68.0, 98.0))
                    for v in ds_crop.data_vars:
                        drop_coords = [c for c in ds_crop[v].coords if c not in ["latitude", "longitude", "time", "valid_time"]]
                        clean_da = ds_crop[v].drop_vars(drop_coords, errors="ignore")
                        if v == "tp":
                            merged["apcp"] = clean_da
                        elif v == "cape":
                            merged["cape"] = clean_da
                        elif v == "gh":
                            merged["hgt_500"] = clean_da
                        elif v == "u":
                            merged["u_850"] = clean_da
                        elif v == "v":
                            merged["v_850"] = clean_da

                merged.attrs["lead_time_hours"] = fxx
                merged.attrs["initialization_time"] = init_str

                if not all(v in merged.data_vars for v in REQUIRED_VARS):
                    raise ValueError(f"Extracted slice missing variables: {[v for v in REQUIRED_VARS if v not in merged.data_vars]}")

                tmp_path = cached_nc.with_suffix(".tmp.nc")
                merged.to_netcdf(str(tmp_path))
                tmp_path.replace(cached_nc)

            elapsed = round(time.time() - t0, 1)
            return (init_str, fxx, "downloaded", elapsed)

        except Exception as e:
            if attempt < max_retries:
                time.sleep(2.0 * attempt)
            else:
                return (init_str, fxx, f"error: {str(e)}", round(time.time() - t0, 1))

    return (init_str, fxx, "failed", round(time.time() - t0, 1))


def download_and_verify_all_gfs(raw_dir: Path, max_workers: int = 6) -> dict:
    """Download all required D2–D9 GFS endpoints concurrently and audit inventory."""
    gfs_dir = raw_dir / "gfs"
    gfs_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print("PHASE 2A: GFS MULTI-LEAD ENDPOINT RETRIEVAL (D2–D9: +51h TO +219h)")
    print("=" * 70)

    # 1. Compile required tasks
    tasks = []
    for month_name, start_date, end_date in COHORTS:
        dates = pd.date_range(start_date, end_date, freq="D")
        for dt in dates:
            init_str = dt.strftime("%Y-%m-%d 00:00")
            for fxx in NEW_ENDPOINTS:
                tasks.append((init_str, fxx, raw_dir))

    total_expected = len(tasks)
    assert total_expected == 720, f"Expected 720 download tasks, got {total_expected}"

    # Check cache status first
    cached_initially = 0
    pending_tasks = []
    for t in tasks:
        init_str, fxx, _ = t
        dt_compact = init_str[:10].replace("-", "")
        cached_nc = gfs_dir / f"gfs_{dt_compact}_f{fxx:02d}.nc"
        if is_valid_cached_slice(cached_nc):
            cached_initially += 1
        else:
            pending_tasks.append(t)

    print(f"Total slices required: {total_expected}")
    print(f"Already cached & valid: {cached_initially}")
    print(f"Pending retrieval:      {len(pending_tasks)}")

    downloaded = 0
    failed = []

    if pending_tasks:
        print(f"\nInitiating concurrent retrieval across {max_workers} worker threads...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {executor.submit(fetch_and_save_slice, t): t for t in pending_tasks}
            completed = 0
            for future in concurrent.futures.as_completed(future_to_task):
                completed += 1
                init_str, fxx, status, elapsed = future.result()
                if status == "downloaded":
                    downloaded += 1
                    print(f"[{completed + cached_initially}/{total_expected}] {init_str} f{fxx:02d}: downloaded ({elapsed}s)")
                elif status == "cached":
                    print(f"[{completed + cached_initially}/{total_expected}] {init_str} f{fxx:02d}: cached")
                else:
                    print(f"[ERROR] [{completed + cached_initially}/{total_expected}] {init_str} f{fxx:02d}: {status}")
                    failed.append((init_str, fxx, status))

    # 2. Strict Machine-Checkable Inventory Audit
    print("\nRunning Machine-Checkable Download Inventory Audit...")
    audit = {
        "total_expected": 720,
        "valid_count": 0,
        "missing_files": [],
        "corrupt_files": [],
    }

    for month_name, start_date, end_date in COHORTS:
        dates = pd.date_range(start_date, end_date, freq="D")
        for dt in dates:
            dt_compact = dt.strftime("%Y%m%d")
            for fxx in NEW_ENDPOINTS:
                nc_path = gfs_dir / f"gfs_{dt_compact}_f{fxx:02d}.nc"
                if not nc_path.exists():
                    audit["missing_files"].append(str(nc_path.name))
                elif not is_valid_cached_slice(nc_path):
                    audit["corrupt_files"].append(str(nc_path.name))
                else:
                    audit["valid_count"] += 1

    print(f"Audit Summary: {audit['valid_count']}/{audit['total_expected']} valid files.")
    if audit["missing_files"] or audit["corrupt_files"]:
        print(f"MISSING FILES: {len(audit['missing_files'])} -> {audit['missing_files'][:5]}")
        print(f"CORRUPT FILES: {len(audit['corrupt_files'])} -> {audit['corrupt_files'][:5]}")
        raise RuntimeError(
            f"GFS download integrity check failed: {len(audit['missing_files'])} missing, "
            f"{len(audit['corrupt_files'])} corrupt. STOPPING model phase as required."
        )

    print("Download integrity validation PASSED: 100% of required GFS endpoints are verified.\n")
    return audit


def build_monthly_d2_d9_matrix(
    start_init: str,
    end_init: str,
    month_name: str,
    raw_dir: Path,
    output_parquet: Path,
    ref_coords: pd.DataFrame,
    full_imd_ds: xr.Dataset,
) -> pd.DataFrame:
    """Build single month's D2–D9 feature matrix and save to Parquet."""
    print(f"\n=======================================================")
    print(f"Constructing D2–D9 Matrix: {month_name.upper()} 2023 ({start_init} to {end_init})")
    print(f"=======================================================")

    gfs_dir = raw_dir / "gfs"
    init_dates = pd.date_range(start_init, end_init, freq="D")
    daily_records = []

    t_start = time.time()
    for day_idx, init_dt in enumerate(init_dates):
        init_str = init_dt.strftime("%Y-%m-%d 00:00")
        dt_compact = init_dt.strftime("%Y%m%d")

        # Load all endpoints for this init day
        gfs_datasets = {}
        for fxx in ALL_REQUIRED_ENDPOINTS:
            nc_path = gfs_dir / f"gfs_{dt_compact}_f{fxx:02d}.nc"
            ds = xr.open_dataset(nc_path)
            gfs_datasets[fxx] = ds

        # Build each lead day D2 through D9
        for lead in range(2, 10):
            f_start = 24 * (lead - 1) + 3
            f_end = 24 * lead + 3
            lead_hours = lead * 24

            valid_dt = init_dt + pd.Timedelta(days=lead)
            valid_str = valid_dt.strftime("%Y-%m-%d")

            # Extract observation for valid date
            imd_slice = full_imd_ds.sel(time=valid_str).sel(lat=slice(8.0, 36.0), lon=slice(68.0, 98.0))
            rain_raw = imd_slice["rain"].values
            rain_clean = np.where(rain_raw == -999.0, np.nan, rain_raw)

            # Nearest-neighbor spatial regridding
            gfs_s = gfs_datasets[f_start].interp(latitude=imd_slice.lat, longitude=imd_slice.lon, method="nearest")
            gfs_e = gfs_datasets[f_end].interp(latitude=imd_slice.lat, longitude=imd_slice.lon, method="nearest")

            diff_apcp = gfs_e["apcp"].values - gfs_s["apcp"].values
            f_apcp_24h = np.maximum(diff_apcp, 0.0)

            lon_2d, lat_2d = np.meshgrid(imd_slice.lon.values, imd_slice.lat.values)
            lead_df = pd.DataFrame({
                "init_time": pd.Timestamp(init_str[:10]),
                "valid_time": pd.Timestamp(valid_str),
                "lead_day": int(lead),
                "lat": lat_2d.ravel(),
                "lon": lon_2d.ravel(),
                "lead_time_hours": int(lead_hours),
                "f_apcp_24h": f_apcp_24h.ravel(),
                "o_rain_24h": rain_clean.ravel(),
                "f_cape": gfs_e["cape"].values.ravel(),
                "f_hgt_500": gfs_e["hgt_500"].values.ravel(),
                "f_u_850": gfs_e["u_850"].values.ravel(),
                "f_v_850": gfs_e["v_850"].values.ravel(),
            })

            # Align strictly with authoritative August active land cells (4,905 points)
            clean_slice = ref_coords.merge(lead_df, on=["lat", "lon"], how="inner")
            clean_slice["error_abs"] = np.abs(clean_slice["f_apcp_24h"] - clean_slice["o_rain_24h"])
            clean_slice["is_bust"] = (
                (clean_slice["error_abs"] > 25.0) &
                ((clean_slice["f_apcp_24h"] > 10.0) | (clean_slice["o_rain_24h"] > 10.0))
            ).astype(int)

            clean_slice = clean_slice[STANDARD_COLUMNS]
            daily_records.append(clean_slice)

        # Close dataset handles for this init date
        for ds in gfs_datasets.values():
            ds.close()

        print(f"[{day_idx + 1}/{len(init_dates)}] Processed {init_str[:10]} (leads D2–D9: 8 × 4,905 = 39,240 cells)")

    full_month_df = pd.concat(daily_records, ignore_index=True)
    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    full_month_df.to_parquet(str(output_parquet), index=False)
    elapsed = time.time() - t_start

    print(f"Saved {output_parquet.name} ({len(full_month_df):,} rows in {elapsed:.1f}s)")
    return full_month_df


def validate_d2_d9_matrix(parquet_path: Path, month_name: str, ref_coords: pd.DataFrame) -> dict:
    """Perform rigorous validation of Phase 2A monthly D2–D9 matrix against all requirements."""
    print(f"\n--- Auditing Matrix: {parquet_path.name} ---")
    assert parquet_path.exists(), f"Parquet file not found: {parquet_path}"
    df = pd.read_parquet(str(parquet_path))

    # 1. Exact row count: 30 days * 8 leads * 4,905 cells = 1,177,200 rows
    total_rows = len(df)
    assert total_rows == EXPECTED_ROWS_PER_MONTH, f"Row count mismatch: {total_rows} != {EXPECTED_ROWS_PER_MONTH}"

    # 2. Schema check
    assert list(df.columns) == STANDARD_COLUMNS, f"Schema mismatch: {list(df.columns)} != {STANDARD_COLUMNS}"

    # 3. Initialization dates check (30 dates)
    init_dates = df["init_time"].unique()
    assert len(init_dates) == 30, f"Expected 30 init dates, got {len(init_dates)}"

    # 4. Lead days check: exactly [2, 3, 4, 5, 6, 7, 8, 9]
    lead_days = sorted(df["lead_day"].unique())
    assert lead_days == [2, 3, 4, 5, 6, 7, 8, 9], f"Unexpected lead days: {lead_days}"

    # 5. Exactly 4,905 cells per init/lead instance
    counts_per_group = df.groupby(["init_time", "lead_day"]).size()
    assert (counts_per_group == EXPECTED_CELLS_PER_SLICE).all(), "Found init/lead group without exactly 4,905 cells!"

    # 6. Valid date alignment check: valid_time == init_time + lead_day
    init_ts = pd.to_datetime(df["init_time"])
    valid_ts = pd.to_datetime(df["valid_time"])
    lead_deltas = pd.to_timedelta(df["lead_day"], unit="D")
    date_diff = (valid_ts - (init_ts + lead_deltas)).dt.total_seconds()
    assert (date_diff == 0).all(), "Valid date does not match init_time + lead_day!"

    # 7. Zero NaN and zero Inf
    nan_count = int(df.isna().sum().sum())
    assert nan_count == 0, f"Found {nan_count} NaNs in dataset"
    numeric_cols = ["f_apcp_24h", "o_rain_24h", "f_cape", "f_hgt_500", "f_u_850", "f_v_850", "error_abs"]
    inf_count = int(np.isinf(df[numeric_cols].values).sum())
    assert inf_count == 0, f"Found {inf_count} Infs in dataset"

    # 8. Non-negative precipitation
    assert (df["f_apcp_24h"] >= 0.0).all(), "Found negative forecast precipitation"
    assert (df["o_rain_24h"] >= 0.0).all(), "Found negative observation precipitation"

    # 9. No duplicate init_time + lead_day + lat + lon
    dup_count = int(df.duplicated(subset=["init_time", "lead_day", "lat", "lon"]).sum())
    assert dup_count == 0, f"Found {dup_count} duplicate coordinate-lead entries"

    # 10. Exact bust label recomputation
    recomputed_bust = (
        (np.abs(df["f_apcp_24h"] - df["o_rain_24h"]) > 25.0) &
        ((df["f_apcp_24h"] > 10.0) | (df["o_rain_24h"] > 10.0))
    ).astype(int)
    bust_mismatches = int((df["is_bust"] != recomputed_bust).sum())
    assert bust_mismatches == 0, f"Bust definition mismatch: {bust_mismatches} errors"

    # 11. Exact coordinate set match with August reference
    df_coords = df[["lat", "lon"]].drop_duplicates().sort_values(["lat", "lon"]).reset_index(drop=True)
    assert len(df_coords) == EXPECTED_CELLS_PER_SLICE, f"Unique cell count mismatch: {len(df_coords)}"
    coord_diff = df_coords.merge(ref_coords, on=["lat", "lon"], how="outer", indicator=True)
    mismatches = int((coord_diff["_merge"] != "both").sum())
    assert mismatches == 0, f"Coordinate mismatch with August reference: {mismatches} cells"

    total_busts = int(df["is_bust"].sum())
    prevalence = round((total_busts / total_rows) * 100.0, 2)
    print(f"Validation PASSED: {month_name.upper()} matrix is complete and verified.")
    print(f"  Rows: {total_rows:,} | Active Cells: 4,905 | NaNs: 0 | Infs: 0")
    print(f"  Total Busts: {total_busts:,} ({prevalence}% prevalence)")

    return {
        "month": month_name,
        "rows": total_rows,
        "active_cells": EXPECTED_CELLS_PER_SLICE,
        "nan_count": nan_count,
        "inf_count": inf_count,
        "total_busts": total_busts,
        "bust_prevalence_pct": prevalence,
    }


def main():
    parser = argparse.ArgumentParser(description="VISHWAS Phase 2A D2–D9 Data Pipeline")
    parser.add_argument("--download-only", action="store_true", help="Run only GFS download and verification")
    parser.add_argument("--build-only", action="store_true", help="Run only matrix building and validation")
    parser.add_argument("--workers", type=int, default=6, help="Concurrent worker threads for downloads")
    args = parser.parse_args()

    raw_dir = Path("backend/data/real/raw")
    features_dir = Path("backend/data/real/features")

    # Step 1: Download and verify all GFS endpoints
    if not args.build_only:
        download_and_verify_all_gfs(raw_dir=raw_dir, max_workers=args.workers)

    if args.download_only:
        print("\n--download-only specified. Exiting after successful download and verification.")
        return

    # Step 2: Load Reference Coordinates and IMD dataset
    ref_parquet = features_dir / "august_2023_matrix.parquet"
    assert ref_parquet.exists(), f"Reference August baseline matrix missing: {ref_parquet}"
    ref_coords = (
        pd.read_parquet(str(ref_parquet))[["lat", "lon"]]
        .drop_duplicates()
        .sort_values(["lat", "lon"])
        .reset_index(drop=True)
    )
    assert len(ref_coords) == EXPECTED_CELLS_PER_SLICE

    rain_file = raw_dir / "rain" / "2023.grd"
    assert rain_file.exists(), f"IMD 2023.grd missing: {rain_file}"
    print(f"\n[IMD] Opening cached IMD 2023 grid: {rain_file}")
    imd_obj = imdlib.open_data("rain", 2023, 2023, "yearwise", str(raw_dir))
    full_imd_ds = imd_obj.get_xarray()

    # Step 3: Build and Validate Matrices for All 3 Months
    audit_results = []
    for month_name, start_date, end_date in COHORTS:
        out_parquet = features_dir / f"{month_name}_2023_d2_d9.parquet"
        build_monthly_d2_d9_matrix(
            start_init=start_date,
            end_init=end_date,
            month_name=month_name,
            raw_dir=raw_dir,
            output_parquet=out_parquet,
            ref_coords=ref_coords,
            full_imd_ds=full_imd_ds,
        )
        audit_res = validate_d2_d9_matrix(out_parquet, month_name, ref_coords)
        audit_results.append(audit_res)

    print("\n" + "=" * 70)
    print("PHASE 2A D2–D9 DATA MATRICES SUMMARY (TABLE A)")
    print("=" * 70)
    print(f"{'Month':<12} | {'Leads':<6} | {'Rows':<11} | {'Active Cells':<12} | {'NaN':<5} | {'Inf':<5} | {'Bust Prev'}")
    print("-" * 70)
    total_all_rows = 0
    for res in audit_results:
        total_all_rows += res["rows"]
        print(
            f"{res['month'].capitalize():<12} | D2–D9  | {res['rows']:<11,} | "
            f"{res['active_cells']:<12,} | {res['nan_count']:<5} | {res['inf_count']:<5} | "
            f"{res['bust_prevalence_pct']}%"
        )
    print("-" * 70)
    print(f"Total instances across 3 cohorts: {total_all_rows:,} (Expected: 3,531,600)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
