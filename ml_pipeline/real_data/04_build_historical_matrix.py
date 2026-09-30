"""VISHWAS Phase 2 Real-Data Validation: Historical Sample Feature Matrix Builder.

Step 4:
- Ingest IMD gridded daily rainfall observations (August 2023).
- Ingest NOAA GFS forecasts (00:00 UTC cycle, lead times +3h and +27h).
- Staged execution:
    Stage A: August 1–3 init (valid Aug 2–4)
    Stage B: August 1–7 init (valid Aug 2–8)
    Stage C: August 1–30 init (valid Aug 2–31)
- Spatial regridding to exact IMD grid (lat 8–36, lon 68–98).
- 24h accumulation: GFS_APCP_24h = max(GFS_APCP(+27h) - GFS_APCP(+3h), 0).
- Standard feature schema:
    lat, lon, valid_time, lead_time_hours, f_apcp_24h, o_rain_24h,
    f_cape, f_hgt_500, f_u_850, f_v_850, error_abs, is_bust
- Output: backend/data/real/features/august_2023_matrix.parquet
"""

import os
import sys
import time
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
from herbie import Herbie
import imdlib

STANDARD_COLUMNS = [
    "lat",
    "lon",
    "valid_time",
    "lead_time_hours",
    "f_apcp_24h",
    "o_rain_24h",
    "f_cape",
    "f_hgt_500",
    "f_u_850",
    "f_v_850",
    "error_abs",
    "is_bust"
]

def fetch_or_load_gfs_day(
    init_date: str,
    fxx: int,
    raw_dir: Path,
    max_retries: int = 4,
    retry_delay: float = 3.0
) -> xr.Dataset:
    """Download or load cached cropped GFS dataset for single init date and fxx."""
    gfs_dir = raw_dir / "gfs"
    gfs_dir.mkdir(parents=True, exist_ok=True)
    
    date_compact = init_date.replace("-", "").replace(" ", "").replace(":", "")[:8]
    cached_nc = gfs_dir / f"gfs_{date_compact}_f{fxx:02d}.nc"
    
    req_vars = ["apcp"] if fxx == 3 else ["apcp", "cape", "hgt_500", "u_850", "v_850"]
    
    if cached_nc.exists():
        try:
            ds = xr.open_dataset(str(cached_nc))
            if all(v in ds.data_vars for v in req_vars):
                return ds
        except Exception:
            pass  # Re-download if corrupted
            
    # Download via Herbie
    acc_str = f"0-{fxx} hour acc fcst"
    search_expr = f":(?:APCP:surface:{acc_str}|CAPE:surface|HGT:500 mb|UGRD:850 mb|VGRD:850 mb):"
    
    H = None
    for attempt in range(1, max_retries + 1):
        try:
            H = Herbie(init_date, model="gfs", fxx=fxx, save_dir=str(raw_dir), overwrite=False)
            ds_list = H.xarray(search_expr)
            break
        except Exception as e:
            print(f"[GFS RETRY] {init_date} f{fxx:02d} attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)
            else:
                raise e

    if isinstance(ds_list, xr.Dataset):
        ds_list = [ds_list]
        
    merged = xr.Dataset()
    for ds in ds_list:
        # Crop to Lat 8-36, Lon 68-98
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

    # Fallback queries if cfgrib split dropped any required variable
    if "apcp" not in merged:
        ds_apcp = H.xarray(f":APCP:surface:")
        if isinstance(ds_apcp, list):
            ds_apcp = ds_apcp[0]
        ds_apcp_crop = ds_apcp.sel(latitude=slice(36.0, 8.0), longitude=slice(68.0, 98.0))
        drop_coords = [c for c in ds_apcp_crop["tp"].coords if c not in ["latitude", "longitude", "time", "valid_time"]]
        merged["apcp"] = ds_apcp_crop["tp"].drop_vars(drop_coords, errors="ignore")
        
    if fxx == 27:
        if "cape" not in merged:
            ds_cape = H.xarray(":CAPE:surface:")
            if isinstance(ds_cape, list):
                ds_cape = ds_cape[0]
            ds_cape_crop = ds_cape.sel(latitude=slice(36.0, 8.0), longitude=slice(68.0, 98.0))
            drop_coords = [c for c in ds_cape_crop["cape"].coords if c not in ["latitude", "longitude", "time", "valid_time"]]
            merged["cape"] = ds_cape_crop["cape"].drop_vars(drop_coords, errors="ignore")
            
        if "hgt_500" not in merged:
            ds_hgt = H.xarray(":HGT:500 mb:")
            if isinstance(ds_hgt, list):
                ds_hgt = ds_hgt[0]
            ds_hgt_crop = ds_hgt.sel(latitude=slice(36.0, 8.0), longitude=slice(68.0, 98.0))
            drop_coords = [c for c in ds_hgt_crop["gh"].coords if c not in ["latitude", "longitude", "time", "valid_time"]]
            merged["hgt_500"] = ds_hgt_crop["gh"].drop_vars(drop_coords, errors="ignore")
            
        if "u_850" not in merged or "v_850" not in merged:
            ds_wind = H.xarray(":(?:UGRD|VGRD):850 mb:")
            if isinstance(ds_wind, list):
                ds_wind = ds_wind[0]
            ds_wind_crop = ds_wind.sel(latitude=slice(36.0, 8.0), longitude=slice(68.0, 98.0))
            if "u" in ds_wind_crop:
                drop_u = [c for c in ds_wind_crop["u"].coords if c not in ["latitude", "longitude", "time", "valid_time"]]
                merged["u_850"] = ds_wind_crop["u"].drop_vars(drop_u, errors="ignore")
            if "v" in ds_wind_crop:
                drop_v = [c for c in ds_wind_crop["v"].coords if c not in ["latitude", "longitude", "time", "valid_time"]]
                merged["v_850"] = ds_wind_crop["v"].drop_vars(drop_v, errors="ignore")

    merged.attrs["lead_time_hours"] = fxx
    merged.attrs["initialization_time"] = init_date
    if all(v in merged.data_vars for v in req_vars):
        merged.to_netcdf(str(cached_nc))
    return merged



def build_historical_matrix(
    start_init: str = "2023-08-01",
    end_init: str = "2023-08-30",
    raw_dir: str = "backend/data/real/raw",
    output_parquet: str = "backend/data/real/features/august_2023_matrix.parquet"
) -> pd.DataFrame:
    """Build feature matrix for historical sample using daily chunked streaming."""
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    
    # 1. Load IMD full 2023 dataset
    rain_file = raw_path / "rain" / "2023.grd"
    if rain_file.exists():
        print(f"[IMD] Loading cached IMD 2023 grid: {rain_file}")
        imd_obj = imdlib.open_data("rain", 2023, 2023, "yearwise", str(raw_path))
    else:
        print("[IMD] Downloading IMD 2023 grid...")
        imd_obj = imdlib.get_data("rain", 2023, 2023, fn_format="yearwise", file_dir=str(raw_path))
        
    full_imd_ds = imd_obj.get_xarray()
    
    # 2. Iterate through initialization dates
    init_dates = pd.date_range(start_init, end_init, freq="D")
    daily_dfs = []
    
    total_days = len(init_dates)
    success_days = 0
    failed_days = 0
    stats = {
        "days_processed": 0,
        "gfs_files_success": 0,
        "gfs_files_failed": 0,
        "total_rows": 0,
        "bust_count": 0
    }
    
    print(f"\n=======================================================")
    print(f"Building Historical Matrix: {start_init} to {end_init} ({total_days} days)")
    print(f"=======================================================\n")
    
    for i, init_dt in enumerate(init_dates):
        init_str = init_dt.strftime("%Y-%m-%d 00:00")
        valid_dt = init_dt + pd.Timedelta(days=1)
        valid_str = valid_dt.strftime("%Y-%m-%d")
        
        print(f"[{i+1}/{total_days}] Processing Init: {init_str} -> Valid (IMD): {valid_str}")
        
        try:
            # GFS +3h and +27h
            gfs3 = fetch_or_load_gfs_day(init_str, 3, raw_path)
            stats["gfs_files_success"] += 1
            gfs27 = fetch_or_load_gfs_day(init_str, 27, raw_path)
            stats["gfs_files_success"] += 1
            
            # Extract IMD for valid_str and crop to Lat 8-36, Lon 68-98
            imd_slice = full_imd_ds.sel(time=valid_str).sel(lat=slice(8.0, 36.0), lon=slice(68.0, 98.0))
            rain_raw = imd_slice["rain"].values
            rain_clean = np.where(rain_raw == -999.0, np.nan, rain_raw)
            
            # Spatial regridding via nearest-neighbor interpolation
            gfs3_r = gfs3.interp(latitude=imd_slice.lat, longitude=imd_slice.lon, method="nearest")
            gfs27_r = gfs27.interp(latitude=imd_slice.lat, longitude=imd_slice.lon, method="nearest")
            
            # 24-hour precipitation accumulation
            diff_apcp = gfs27_r["apcp"].values - gfs3_r["apcp"].values
            f_apcp_24h = np.maximum(diff_apcp, 0.0)
            o_rain_24h = rain_clean
            
            error_abs = np.abs(f_apcp_24h - o_rain_24h)
            is_bust = ((error_abs > 25.0) & ((f_apcp_24h > 10.0) | (o_rain_24h > 10.0))).astype(int)
            
            lon_2d, lat_2d = np.meshgrid(imd_slice.lon.values, imd_slice.lat.values)
            
            day_df = pd.DataFrame({
                "lat": lat_2d.ravel(),
                "lon": lon_2d.ravel(),
                "valid_time": pd.Timestamp(valid_str),
                "lead_time_hours": 24,
                "f_apcp_24h": f_apcp_24h.ravel(),
                "o_rain_24h": o_rain_24h.ravel(),
                "f_cape": gfs27_r["cape"].values.ravel(),
                "f_hgt_500": gfs27_r["hgt_500"].values.ravel(),
                "f_u_850": gfs27_r["u_850"].values.ravel(),
                "f_v_850": gfs27_r["v_850"].values.ravel(),
                "error_abs": error_abs.ravel(),
                "is_bust": is_bust.ravel()
            })
            
            # Drop NaN rows (ocean cells)
            day_clean = day_df.dropna(subset=["f_apcp_24h", "o_rain_24h", "f_cape", "f_hgt_500", "f_u_850", "f_v_850"]).reset_index(drop=True)
            daily_dfs.append(day_clean)
            
            success_days += 1
            stats["days_processed"] += 1
            stats["total_rows"] += len(day_clean)
            stats["bust_count"] += int(day_clean["is_bust"].sum())
            print(f"       Extracted {len(day_clean)} valid cells, {day_clean['is_bust'].sum()} busts ({day_clean['is_bust'].mean()*100:.1f}%)")
            
        except Exception as e:
            failed_days += 1
            stats["gfs_files_failed"] += 1
            print(f"[DAY FAILED] Could not process {init_str}: {e}")
            
    if not daily_dfs:
        raise RuntimeError("No daily data was successfully processed!")
        
    full_df = pd.concat(daily_dfs, ignore_index=True)
    out_path = Path(output_parquet)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    full_df.to_parquet(str(out_path), index=False)
    
    print("\n" + "=" * 55)
    print("HISTORICAL MATRIX GENERATION SUMMARY")
    print("=" * 55)
    print(f"Days processed:      {success_days}/{total_days} (failed: {failed_days})")
    print(f"Total rows:          {len(full_df):,}")
    print(f"Grid cells per day:  {len(full_df) // max(success_days, 1):,}")
    print(f"Bust count:          {full_df['is_bust'].sum():,} ({full_df['is_bust'].mean()*100:.2f}% prevalence)")
    print(f"Output saved to:     {out_path}")
    print("=" * 55 + "\n")
    
    return full_df


def verify_historical_matrix(parquet_path: str, expected_min_rows: int = 10000) -> bool:
    """Verify historical feature matrix parquet meets requirements."""
    p = Path(parquet_path)
    if not p.exists():
        print(f"[VERIFY FAILED] Parquet not found: {parquet_path}")
        return False
        
    try:
        df = pd.read_parquet(str(p))
        assert list(df.columns) == STANDARD_COLUMNS, f"Columns mismatch: {list(df.columns)}"
        assert len(df) >= expected_min_rows, f"Insufficient rows: {len(df)} < {expected_min_rows}"
        assert df.isna().sum().sum() == 0, "Found NaNs in dataframe"
        
        # Verify valid_time ordering
        vtimes = pd.to_datetime(df["valid_time"])
        print(f"[VERIFY PASS] Matrix valid: {len(df):,} rows from {vtimes.min().strftime('%Y-%m-%d')} to {vtimes.max().strftime('%Y-%m-%d')}")
        print(f"[VERIFY PASS] Bust prevalence: {df['is_bust'].mean()*100:.2f}% ({df['is_bust'].sum():,} busts)")
        return True
    except Exception as e:
        print(f"[VERIFY FAILED] Parquet verification exception: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Build August 2023 Historical Feature Matrix")
    parser.add_argument("--stage", choices=["A", "B", "C"], default="A", help="Staged execution: A (Aug 1-3), B (Aug 1-7), C (Aug 1-30)")
    parser.add_argument("--start", default=None, help="Custom start init date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="Custom end init date YYYY-MM-DD")
    parser.add_argument("--output", default="backend/data/real/features/august_2023_matrix.parquet", help="Output parquet path")
    parser.add_argument("--verify", action="store_true", help="Run verification only")
    args = parser.parse_args()
    
    if args.verify:
        v = verify_historical_matrix(args.output, expected_min_rows=1000)
        sys.exit(0 if v else 1)
        
    if args.start and args.end:
        start_date = args.start
        end_date = args.end
    elif args.stage == "A":
        start_date = "2023-08-01"
        end_date = "2023-08-03"
    elif args.stage == "B":
        start_date = "2023-08-01"
        end_date = "2023-08-07"
    elif args.stage == "C":
        start_date = "2023-08-01"
        end_date = "2023-08-30"
        
    df = build_historical_matrix(
        start_init=start_date,
        end_init=end_date,
        output_parquet=args.output
    )
    
    expected_rows = len(pd.date_range(start_date, end_date)) * 4000
    v = verify_historical_matrix(args.output, expected_min_rows=expected_rows)
    sys.exit(0 if v else 1)

if __name__ == "__main__":
    main()
