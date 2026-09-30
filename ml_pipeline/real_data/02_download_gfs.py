"""VISHWAS Phase 2 Real-Data Validation: Download & Extract NOAA GFS NWP.

Step 2:
- Download GFS 0.25-deg forecasts using Herbie.
- Target initialization: 2023-08-01 00:00 UTC.
- Lead times: +3h and +27h.
- Required variables:
  - APCP surface (0-3h and 0-27h accumulated precipitation)
  - CAPE surface
  - HGT 500 mb
  - UGRD 850 mb
  - VGRD 850 mb
- Crop to India bounding box (Lat 8.0 - 36.0, Lon 68.0 - 98.0).
- Save to:
  backend/data/real/raw/gfs_test_3h.nc
  backend/data/real/raw/gfs_test_27h.nc
"""

import os
import sys
import argparse
from pathlib import Path
import numpy as np
import xarray as xr
from herbie import Herbie

def download_and_extract_gfs(
    date_str: str = "2023-08-01 00:00",
    fxx: int = 3,
    output_path: str = "backend/data/real/raw/gfs_test_3h.nc",
    save_dir: str = "backend/data/real/raw",
    max_retries: int = 4,
    retry_delay: float = 3.0
) -> xr.Dataset:
    """Download GFS forecast subset for given init date and lead time fxx, crop domain, and save netCDF."""
    import time
    print(f"[GFS] Initializing Herbie for {date_str} UTC, fxx={fxx}h...")
    
    # Construct exact search expression
    acc_str = f"0-{fxx} hour acc fcst"
    search_expr = f":(?:APCP:surface:{acc_str}|CAPE:surface|HGT:500 mb|UGRD:850 mb|VGRD:850 mb):"
    print(f"[GFS] Search regex: {search_expr}")
    
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            H = Herbie(date_str, model="gfs", fxx=fxx, save_dir=save_dir, overwrite=False)
            ds_list = H.xarray(search_expr)
            break
        except Exception as e:
            last_err = e
            print(f"[GFS WARNING] Attempt {attempt}/{max_retries} failed for {date_str} fxx={fxx}: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)
            else:
                raise last_err

    if isinstance(ds_list, xr.Dataset):
        ds_list = [ds_list]
        
    merged = xr.Dataset()
    for ds in ds_list:
        # Crop to Lat 8-36, Lon 68-98
        # GFS latitude is descending (90 -> -90), longitude is ascending (0 -> 360)
        ds_crop = ds.sel(latitude=slice(36.0, 8.0), longitude=slice(68.0, 98.0))
        for v in ds_crop.data_vars:
            drop_coords = [c for c in ds_crop[v].coords if c not in ["latitude", "longitude", "time", "valid_time"]]
            clean_da = ds_crop[v].drop_vars(drop_coords, errors="ignore")
            if v == "tp":
                merged["apcp"] = clean_da
                merged["apcp"].attrs["description"] = f"Accumulated precipitation (0 to {fxx}h)"
                merged["apcp"].attrs["units"] = "kg m**-2 (mm)"
            elif v == "cape":
                merged["cape"] = clean_da
                merged["cape"].attrs["description"] = "Surface convective available potential energy"
                merged["cape"].attrs["units"] = "J kg**-1"
            elif v == "gh":
                merged["hgt_500"] = clean_da
                merged["hgt_500"].attrs["description"] = "500 hPa Geopotential Height"
                merged["hgt_500"].attrs["units"] = "gpm"
            elif v == "u":
                merged["u_850"] = clean_da
                merged["u_850"].attrs["description"] = "850 hPa U-component of wind"
                merged["u_850"].attrs["units"] = "m s**-1"
            elif v == "v":
                merged["v_850"] = clean_da
                merged["v_850"].attrs["description"] = "850 hPa V-component of wind"
                merged["v_850"].attrs["units"] = "m s**-1"
                
    merged.attrs["lead_time_hours"] = fxx
    merged.attrs["model"] = "NOAA-GFS-0.25deg"
    merged.attrs["initialization_time"] = date_str
    
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    merged.to_netcdf(str(out_file))
    print(f"[GFS] Saved cropped GFS NetCDF to {out_file}")
    print(f"[GFS] Variables: {list(merged.data_vars.keys())}")
    print(f"[GFS] Coordinates: lat {len(merged.latitude)} cells ({float(merged.latitude.min())} to {float(merged.latitude.max())}), "
          f"lon {len(merged.longitude)} cells ({float(merged.longitude.min())} to {float(merged.longitude.max())})")
    return merged


def verify_gfs_file(filepath: str, expected_fxx: int, expected_init: str = "2023-08-01") -> bool:
    """Verify GFS test file meets all M1 specifications."""
    p = Path(filepath)
    if not p.exists():
        print(f"[VERIFY FAILED] File does not exist: {filepath}")
        return False
        
    try:
        with xr.open_dataset(str(p)) as ds:
            # 1. Coordinates exist
            assert "latitude" in ds.coords, "Missing 'latitude' coordinate"
            assert "longitude" in ds.coords, "Missing 'longitude' coordinate"
            assert "time" in ds.coords or "valid_time" in ds.coords, "Missing time/valid_time coordinate"
            
            # 2. Required variables exist
            req_vars = ["apcp", "cape", "hgt_500", "u_850", "v_850"]
            for v in req_vars:
                assert v in ds.data_vars, f"Missing required variable: {v}"
                
            # 3. Dimensions are non-empty
            assert len(ds.latitude) > 0, "Latitude dimension is empty"
            assert len(ds.longitude) > 0, "Longitude dimension is empty"
            
            # 4. Lat/lon range is within [8, 36] and [68, 98]
            assert 8.0 <= float(ds.latitude.min()) and float(ds.latitude.max()) <= 36.0, f"Lat out of range: {ds.latitude.min()}..{ds.latitude.max()}"
            assert 68.0 <= float(ds.longitude.min()) and float(ds.longitude.max()) <= 98.0, f"Lon out of range: {ds.longitude.min()}..{ds.longitude.max()}"
            
            # 5. Timestamp check
            init_str = str(ds.time.values)[:10]
            assert init_str == expected_init, f"Unexpected initialization timestamp: {init_str} (expected {expected_init})"
            
            # 6. Attributes / Lead time check
            assert int(ds.attrs.get("lead_time_hours", 0)) == expected_fxx, f"Lead time mismatch: got {ds.attrs.get('lead_time_hours')} expected {expected_fxx}"
            
            print(f"[VERIFY PASS] GFS file {filepath} (F{expected_fxx:02d}) verified successfully: shape=({len(ds.latitude)}, {len(ds.longitude)}), init={init_str}")
            return True
    except Exception as e:
        print(f"[VERIFY FAILED] Exception verifying GFS file: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download and extract NOAA GFS data")
    parser.add_argument("--date", default="2023-08-01 00:00", help="Init time YYYY-MM-DD HH:MM")
    parser.add_argument("--out-3h", default="backend/data/real/raw/gfs_test_3h.nc", help="Output path for +3h")
    parser.add_argument("--out-27h", default="backend/data/real/raw/gfs_test_27h.nc", help="Output path for +27h")
    parser.add_argument("--verify", action="store_true", help="Run verification only")
    args = parser.parse_args()
    
    if args.verify:
        v3 = verify_gfs_file(args.out_3h, 3)
        v27 = verify_gfs_file(args.out_27h, 27)
        sys.exit(0 if (v3 and v27) else 1)
        
    print("=== Downloading GFS +3h ===")
    download_and_extract_gfs(date_str=args.date, fxx=3, output_path=args.out_3h)
    
    print("\n=== Downloading GFS +27h ===")
    download_and_extract_gfs(date_str=args.date, fxx=27, output_path=args.out_27h)
    
    print("\n=== Verifying GFS Datasets ===")
    v3 = verify_gfs_file(args.out_3h, 3)
    v27 = verify_gfs_file(args.out_27h, 27)
    
    sys.exit(0 if (v3 and v27) else 1)

if __name__ == "__main__":
    main()
