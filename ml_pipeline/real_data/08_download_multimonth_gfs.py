"""VISHWAS Phase 1B: Retrieve and Verify NOAA GFS 0.25° Data for July and September 2023.

Retrieves:
1. July 2023:
   - Init dates: 2023-07-01 to 2023-07-30 (30 days)
   - Lead times: +3h and +27h (60 cropped NetCDF files)
   - Valid IMD accumulation window: 2023-07-02 to 2023-07-31

2. September 2023:
   - Init dates: 2023-08-31 to 2023-09-29 (30 days)
   - Lead times: +3h and +27h (60 cropped NetCDF files)
   - Valid IMD accumulation window: 2023-09-01 to 2023-09-30

Uses Herbie with concurrent threads to download byte-range subsets from NOAA Open Data AWS S3
and crops strictly to the Indian subcontinent (Lat 8-36, Lon 68-98).
"""

import os
import sys
import importlib
from pathlib import Path
import concurrent.futures
import pandas as pd
import xarray as xr

sys.path.insert(0, str(Path(".").resolve()))

# Reconfigure stdout/stderr for Windows console to handle UTF-8 symbols from Herbie
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

mod = importlib.import_module("ml_pipeline.real_data.04_build_historical_matrix")
fetch_or_load_gfs_day = mod.fetch_or_load_gfs_day


def process_single_slice(args):
    """Worker function to check cache or download single GFS slice."""
    init_str, fxx, raw_dir = args
    dt_compact = init_str[:10].replace("-", "")
    gfs_dir = raw_dir / "gfs"
    cached_nc = gfs_dir / f"gfs_{dt_compact}_f{fxx:02d}.nc"
    req_vars = ["apcp"] if fxx == 3 else ["apcp", "cape", "hgt_500", "u_850", "v_850"]

    if cached_nc.exists() and cached_nc.stat().st_size > 0:
        try:
            with xr.open_dataset(cached_nc) as ds:
                if all(v in ds.data_vars for v in req_vars):
                    return (init_str, fxx, "cached")
        except Exception:
            pass

    # Download via Herbie
    fetch_or_load_gfs_day(init_str, fxx, raw_dir)
    return (init_str, fxx, "downloaded")


def download_period(start_date: str, end_date: str, period_name: str, raw_dir: Path, max_workers: int = 4) -> dict:
    """Download GFS +3h and +27h slices concurrently for date range."""
    dates = pd.date_range(start_date, end_date, freq="D")
    total_dates = len(dates)
    total_expected = total_dates * 2
    print(f"\n============================================================")
    print(f"Retrieving GFS Slices for {period_name}: {start_date} to {end_date} ({total_dates} dates / {total_expected} files)")
    print(f"============================================================")

    results = {
        "period": period_name,
        "start_date": start_date,
        "end_date": end_date,
        "total_expected_files": total_expected,
        "downloaded_files": 0,
        "cached_files": 0,
        "failed_files": [],
    }

    gfs_dir = raw_dir / "gfs"
    gfs_dir.mkdir(parents=True, exist_ok=True)

    tasks = []
    for dt in dates:
        init_str = dt.strftime("%Y-%m-%d 00:00")
        for fxx in [3, 27]:
            tasks.append((init_str, fxx, raw_dir))

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {executor.submit(process_single_slice, t): t for t in tasks}
        for future in concurrent.futures.as_completed(future_to_task):
            init_str, fxx, _ = future_to_task[future]
            try:
                res = future.result()
                if res[2] == "cached":
                    results["cached_files"] += 1
                else:
                    results["downloaded_files"] += 1
                done_count = results["cached_files"] + results["downloaded_files"]
                print(f"[PROGRESS] {res[0]} f{res[1]:02d}: {res[2]} ({done_count}/{total_expected})")
            except Exception as e:
                print(f"[ERROR] Failed {init_str} f{fxx:02d}: {e}")
                results["failed_files"].append((init_str, fxx, str(e)))

    print(f"Finished {period_name}: {results['cached_files']} cached, {results['downloaded_files']} downloaded, {len(results['failed_files'])} failed.")
    return results


def validate_period(start_date: str, end_date: str, period_name: str, raw_dir: Path) -> dict:
    """Audit and validate all expected GFS NetCDF files for the period."""
    dates = pd.date_range(start_date, end_date, freq="D")
    gfs_dir = raw_dir / "gfs"

    audit = {
        "period": period_name,
        "expected_files": len(dates) * 2,
        "valid_files": 0,
        "missing_files": [],
        "corrupted_files": [],
        "total_size_bytes": 0,
        "dimensions": None,
        "lat_range": None,
        "lon_range": None,
    }

    for dt in dates:
        date_compact = dt.strftime("%Y%m%d")
        for fxx in [3, 27]:
            nc_path = gfs_dir / f"gfs_{date_compact}_f{fxx:02d}.nc"
            if not nc_path.exists():
                audit["missing_files"].append(nc_path.name)
                continue

            size = nc_path.stat().st_size
            if size == 0:
                audit["corrupted_files"].append((nc_path.name, "zero_byte"))
                continue

            audit["total_size_bytes"] += size
            req_vars = ["apcp"] if fxx == 3 else ["apcp", "cape", "hgt_500", "u_850", "v_850"]

            try:
                with xr.open_dataset(nc_path) as ds:
                    for v in req_vars:
                        if v not in ds.data_vars:
                            audit["corrupted_files"].append((nc_path.name, f"missing_var_{v}"))
                            break
                    else:
                        audit["valid_files"] += 1
                        if audit["dimensions"] is None:
                            audit["dimensions"] = {"latitude": len(ds.latitude), "longitude": len(ds.longitude)}
                            audit["lat_range"] = (float(ds.latitude.min()), float(ds.latitude.max()))
                            audit["lon_range"] = (float(ds.longitude.min()), float(ds.longitude.max()))
            except Exception as e:
                audit["corrupted_files"].append((nc_path.name, str(e)))

    return audit


def main():
    raw_path = Path("backend/data/real/raw")

    # 1. July 2023: 2023-07-01 to 2023-07-30 (60 files)
    july_res = download_period("2023-07-01", "2023-07-30", "July 2023", raw_path, max_workers=4)
    july_audit = validate_period("2023-07-01", "2023-07-30", "July 2023", raw_path)

    # 2. September 2023: 2023-08-31 to 2023-09-29 (60 files)
    sept_res = download_period("2023-08-31", "2023-09-29", "September 2023", raw_path, max_workers=4)
    sept_audit = validate_period("2023-08-31", "2023-09-29", "September 2023", raw_path)

    print("\n" + "=" * 60)
    print("PHASE 1B GFS EXPANSION AUDIT SUMMARY")
    print("=" * 60)
    print(f"July 2023:      {july_audit['valid_files']}/{july_audit['expected_files']} valid files "
          f"({july_audit['total_size_bytes'] / (1024*1024):.2f} MB), Missing: {len(july_audit['missing_files'])}, Corrupted: {len(july_audit['corrupted_files'])}")
    print(f"September 2023: {sept_audit['valid_files']}/{sept_audit['expected_files']} valid files "
          f"({sept_audit['total_size_bytes'] / (1024*1024):.2f} MB), Missing: {len(sept_audit['missing_files'])}, Corrupted: {len(sept_audit['corrupted_files'])}")
    print(f"Grid dimensions: {july_audit['dimensions']}, Lat: {july_audit['lat_range']}, Lon: {july_audit['lon_range']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
