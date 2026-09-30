"""VISHWAS Phase 2 Real-Data Validation: Download & Extract IMD Gridded Rainfall.

Step 1:
- Ingest IMD gridded daily rainfall data (using imdlib).
- Crop to India bounding box (Latitude: 8.0 to 36.0, Longitude: 68.0 to 98.0).
- Replace missing values (-999.0) with NaN.
- Extract requested date (default: 2023-08-02) and save to NetCDF.
"""

import os
import sys
import argparse
from pathlib import Path
import numpy as np
import xarray as xr
import imdlib

def download_and_extract_imd(
    date_str: str = "2023-08-02",
    raw_dir: str = "backend/data/real/raw",
    output_path: str = "backend/data/real/raw/imd_test.nc",
    year: int = 2023
) -> xr.Dataset:
    """Download IMD daily rainfall for given year, extract date, crop domain, and save netCDF."""
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    
    rain_file = raw_path / "rain" / f"{year}.grd"
    if rain_file.exists():
        print(f"[IMD] Found cached IMD grid file: {rain_file}")
        data = imdlib.open_data("rain", year, year, "yearwise", str(raw_path))
    else:
        print(f"[IMD] Downloading IMD daily rainfall for {year} via imdlib...")
        data = imdlib.get_data("rain", year, year, fn_format="yearwise", file_dir=str(raw_path))
    
    ds = data.get_xarray()
    print(f"[IMD] Full dataset loaded: time range {ds.time.values[0]} to {ds.time.values[-1]}")
    
    # Select requested date
    if date_str:
        ds_date = ds.sel(time=date_str)
    else:
        ds_date = ds
        
    # Crop to standard bounding box: Lat 8.0 - 36.0, Lon 68.0 - 98.0
    ds_cropped = ds_date.sel(lat=slice(8.0, 36.0), lon=slice(68.0, 98.0))
    
    # Replace -999.0 missing values with NaN
    rain_data = ds_cropped["rain"].values
    cleaned_rain = np.where(rain_data == -999.0, np.nan, rain_data)
    ds_cropped["rain"] = (ds_cropped["rain"].dims, cleaned_rain)
    
    # Save output
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    ds_cropped.to_netcdf(str(out_file))
    print(f"[IMD] Saved cropped IMD NetCDF to {out_file}")
    print(f"[IMD] Coordinates: lat {len(ds_cropped.lat)} cells ({ds_cropped.lat.values.min()} to {ds_cropped.lat.values.max()}), "
          f"lon {len(ds_cropped.lon)} cells ({ds_cropped.lon.values.min()} to {ds_cropped.lon.values.max()})")
    print(f"[IMD] Non-NaN grid cells: {np.count_nonzero(~np.isnan(cleaned_rain))}")
    return ds_cropped


def verify_imd_file(filepath: str = "backend/data/real/raw/imd_test.nc") -> bool:
    """Verify IMD test file meets all M1 specifications."""
    p = Path(filepath)
    if not p.exists():
        print(f"[VERIFY FAILED] File does not exist: {filepath}")
        return False
    
    try:
        with xr.open_dataset(str(p)) as ds:
            # 1. Coordinates exist
            assert "lat" in ds.coords, "Missing 'lat' coordinate"
            assert "lon" in ds.coords, "Missing 'lon' coordinate"
            assert "time" in ds.coords, "Missing 'time' coordinate"
            
            # 2. Variable exists
            assert "rain" in ds.data_vars, "Missing 'rain' variable"
            
            # 3. Dimensions are non-empty
            assert len(ds.lat) > 0, "Latitude dimension is empty"
            assert len(ds.lon) > 0, "Longitude dimension is empty"
            
            # 4. Lat/lon range is within [8, 36] and [68, 98]
            assert 8.0 <= float(ds.lat.min()) and float(ds.lat.max()) <= 36.0, f"Lat out of range: {ds.lat.min()}..{ds.lat.max()}"
            assert 68.0 <= float(ds.lon.min()) and float(ds.lon.max()) <= 98.0, f"Lon out of range: {ds.lon.min()}..{ds.lon.max()}"
            
            # 5. Timestamp check
            t_str = str(ds.time.values)[:10]
            assert t_str == "2023-08-02", f"Unexpected timestamp: {t_str}"
            
            # 6. Check -999.0 replaced with NaN
            vals = ds.rain.values
            assert not (vals == -999.0).any(), "Found unreplaced -999.0 missing values"
            assert np.isnan(vals).any(), "Expected NaNs over non-land or missing areas"
            
            print(f"[VERIFY PASS] IMD file {filepath} verified successfully: shape={vals.shape}, time={t_str}")
            return True
    except Exception as e:
        print(f"[VERIFY FAILED] Exception verifying IMD file: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download and extract IMD rainfall data")
    parser.add_argument("--date", default="2023-08-02", help="Date in YYYY-MM-DD")
    parser.add_argument("--raw-dir", default="backend/data/real/raw", help="Raw data directory")
    parser.add_argument("--output", default="backend/data/real/raw/imd_test.nc", help="Output NetCDF path")
    parser.add_argument("--verify", action="store_true", help="Run verification only")
    args = parser.parse_args()
    
    if args.verify:
        success = verify_imd_file(args.output)
        sys.exit(0 if success else 1)
        
    download_and_extract_imd(
        date_str=args.date,
        raw_dir=args.raw_dir,
        output_path=args.output
    )
    success = verify_imd_file(args.output)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
