"""VISHWAS Phase 2 Real-Data Validation: Temporal & Spatial Alignment and Error Calculation.

Step 3:
1. Temporal Alignment:
   - IMD daily rainfall measures 24-hour accumulation ending at 08:30 IST (03:00 UTC).
   - GFS 00:00 UTC cycle:
     - GFS(+27h) valid at 03:00 UTC next day.
     - GFS(+3h) valid at 03:00 UTC current day.
     - GFS_APCP_24h = max(GFS_APCP(+27h) - GFS_APCP(+3h), 0)
   - Verified accumulation metadata: GFS APCP at +3h is 0-3h accumulation; at +27h is 0-27h accumulation.
     Their difference gives the exact 24h accumulation.

2. Spatial Alignment:
   - xarray.Dataset.interp(method="nearest") to place GFS fields onto exact IMD coordinate grid.
   - Verification: latitude, longitude, and array dimensions match exactly.

3. Forecast Error & Bust Label:
   - error_abs = abs(f_apcp_24h - o_rain_24h)
   - is_bust = 1 if (error_abs > 25.0 and (f_apcp_24h > 10.0 or o_rain_24h > 10.0)) else 0

4. Output:
   - backend/data/real/features/test_matrix.parquet
   - Standard schema: lat, lon, valid_time, lead_time_hours, f_apcp_24h, o_rain_24h,
     f_cape, f_hgt_500, f_u_850, f_v_850, error_abs, is_bust
"""

import os
import sys
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

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

def align_and_calculate_error(
    imd_path: str = "backend/data/real/raw/imd_test.nc",
    gfs_3h_path: str = "backend/data/real/raw/gfs_test_3h.nc",
    gfs_27h_path: str = "backend/data/real/raw/gfs_test_27h.nc",
    output_parquet: str = "backend/data/real/features/test_matrix.parquet"
) -> pd.DataFrame:
    """Align IMD observation and GFS forecasts, compute error and bust labels, save parquet."""
    print(f"[ALIGN] Opening IMD observation: {imd_path}")
    imd_ds = xr.open_dataset(imd_path)
    
    print(f"[ALIGN] Opening GFS +3h: {gfs_3h_path}")
    gfs3_ds = xr.open_dataset(gfs_3h_path)
    
    print(f"[ALIGN] Opening GFS +27h: {gfs_27h_path}")
    gfs27_ds = xr.open_dataset(gfs_27h_path)
    
    # Verify metadata and timestamps
    init_time_3h = str(gfs3_ds.time.values)[:10]
    init_time_27h = str(gfs27_ds.time.values)[:10]
    assert init_time_3h == init_time_27h, f"GFS initialization mismatch: {init_time_3h} vs {init_time_27h}"
    
    # Spatial regridding to exact IMD coordinate grid using nearest-neighbor interpolation
    print("[ALIGN] Regridding GFS fields to IMD grid via xarray.interp(method='nearest')...")
    gfs3_regrid = gfs3_ds.interp(latitude=imd_ds.lat, longitude=imd_ds.lon, method="nearest")
    gfs27_regrid = gfs27_ds.interp(latitude=imd_ds.lat, longitude=imd_ds.lon, method="nearest")
    
    # Verification: latitude and longitude coordinates match
    np.testing.assert_allclose(gfs3_regrid.latitude.values, imd_ds.lat.values, err_msg="Latitude coords do not match IMD")
    np.testing.assert_allclose(gfs3_regrid.longitude.values, imd_ds.lon.values, err_msg="Longitude coords do not match IMD")
    np.testing.assert_allclose(gfs27_regrid.latitude.values, imd_ds.lat.values, err_msg="Latitude coords do not match IMD")
    np.testing.assert_allclose(gfs27_regrid.longitude.values, imd_ds.lon.values, err_msg="Longitude coords do not match IMD")
    assert gfs27_regrid["apcp"].shape == imd_ds["rain"].shape, f"Shape mismatch: {gfs27_regrid['apcp'].shape} vs {imd_ds['rain'].shape}"
    print(f"[ALIGN] Spatial verification confirmed: Grid shape is {imd_ds['rain'].shape} ({len(imd_ds.lat)} lat x {len(imd_ds.lon)} lon)")
    
    # 24-hour precipitation accumulation: GFS(+27h) - GFS(+3h), clamped to 0
    diff_apcp = gfs27_regrid["apcp"].values - gfs3_regrid["apcp"].values
    f_apcp_24h = np.maximum(diff_apcp, 0.0)
    o_rain_24h = imd_ds["rain"].values
    
    # Error calculation
    error_abs = np.abs(f_apcp_24h - o_rain_24h)
    
    # Bust definition: error_abs > 25.0 and (f_apcp_24h > 10.0 or o_rain_24h > 10.0)
    is_bust = (
        (error_abs > 25.0) & ((f_apcp_24h > 10.0) | (o_rain_24h > 10.0))
    ).astype(int)
    
    # Valid verification time
    valid_time_str = str(imd_ds.time.values)[:10]
    valid_time = pd.Timestamp(valid_time_str)
    
    # 2D coordinate grids
    lon_2d, lat_2d = np.meshgrid(imd_ds.lon.values, imd_ds.lat.values)
    
    # Flatten to tabular dataframe
    df = pd.DataFrame({
        "lat": lat_2d.ravel(),
        "lon": lon_2d.ravel(),
        "valid_time": valid_time,
        "lead_time_hours": 24,
        "f_apcp_24h": f_apcp_24h.ravel(),
        "o_rain_24h": o_rain_24h.ravel(),
        "f_cape": gfs27_regrid["cape"].values.ravel(),
        "f_hgt_500": gfs27_regrid["hgt_500"].values.ravel(),
        "f_u_850": gfs27_regrid["u_850"].values.ravel(),
        "f_v_850": gfs27_regrid["v_850"].values.ravel(),
        "error_abs": error_abs.ravel(),
        "is_bust": is_bust.ravel()
    })
    
    # Drop rows containing NaNs in required fields (e.g. oceanic points where IMD is NaN)
    raw_len = len(df)
    df_clean = df.dropna(subset=["f_apcp_24h", "o_rain_24h", "f_cape", "f_hgt_500", "f_u_850", "f_v_850"]).reset_index(drop=True)
    print(f"[ALIGN] Rows before dropping NaNs: {raw_len}; after dropping NaNs: {len(df_clean)}")
    print(f"[ALIGN] Bust samples count: {df_clean['is_bust'].sum()} ({df_clean['is_bust'].mean()*100:.2f}% prevalence)")
    
    # Save parquet
    out_p = Path(output_parquet)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_parquet(str(out_p), index=False)
    print(f"[ALIGN] Saved feature matrix to {out_p}")
    
    return df_clean


def verify_alignment_parquet(parquet_path: str = "backend/data/real/features/test_matrix.parquet") -> bool:
    """Verify test matrix parquet meets standard schema and numerical integrity."""
    p = Path(parquet_path)
    if not p.exists():
        print(f"[VERIFY FAILED] Parquet file does not exist: {parquet_path}")
        return False
        
    try:
        df = pd.read_parquet(str(p))
        
        # 1. Verify schema
        assert list(df.columns) == STANDARD_COLUMNS, f"Schema mismatch! Got {list(df.columns)}, expected {STANDARD_COLUMNS}"
        
        # 2. Verify non-empty
        assert len(df) > 0, "DataFrame is empty"
        
        # 3. Verify no NaNs
        assert df.isna().sum().sum() == 0, f"Found unexpected NaNs in dataframe:\n{df.isna().sum()}"
        
        # 4. Verify coordinate ranges
        assert (df["lat"] >= 8.0).all() and (df["lat"] <= 36.0).all(), "Latitude outside expected range [8, 36]"
        assert (df["lon"] >= 68.0).all() and (df["lon"] <= 98.0).all(), "Longitude outside expected range [68, 98]"
        
        # 5. Verify non-negative precipitation
        assert (df["f_apcp_24h"] >= 0.0).all(), "Negative GFS precipitation found"
        assert (df["o_rain_24h"] >= 0.0).all(), "Negative IMD rainfall found"
        
        # 6. Verify error_abs and bust definition mathematically
        calc_error = (df["f_apcp_24h"] - df["o_rain_24h"]).abs()
        np.testing.assert_allclose(df["error_abs"].values, calc_error.values, atol=1e-5, err_msg="error_abs does not match abs(f - o)")
        
        calc_bust = ((df["error_abs"] > 25.0) & ((df["f_apcp_24h"] > 10.0) | (df["o_rain_24h"] > 10.0))).astype(int)
        np.testing.assert_array_equal(df["is_bust"].values, calc_bust.values, err_msg="is_bust does not match definition")
        
        print(f"[VERIFY PASS] Parquet {parquet_path} passed all checks ({len(df)} rows, {df['is_bust'].sum()} busts)")
        return True
    except Exception as e:
        print(f"[VERIFY FAILED] Alignment verification failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Align IMD observation and GFS NWP forecasts")
    parser.add_argument("--imd", default="backend/data/real/raw/imd_test.nc", help="IMD netCDF file")
    parser.add_argument("--gfs-3h", default="backend/data/real/raw/gfs_test_3h.nc", help="GFS +3h netCDF file")
    parser.add_argument("--gfs-27h", default="backend/data/real/raw/gfs_test_27h.nc", help="GFS +27h netCDF file")
    parser.add_argument("--output", default="backend/data/real/features/test_matrix.parquet", help="Output parquet path")
    parser.add_argument("--verify", action="store_true", help="Run verification only")
    args = parser.parse_args()
    
    if args.verify:
        success = verify_alignment_parquet(args.output)
        sys.exit(0 if success else 1)
        
    align_and_calculate_error(
        imd_path=args.imd,
        gfs_3h_path=args.gfs_3h,
        gfs_27h_path=args.gfs_27h,
        output_parquet=args.output
    )
    success = verify_alignment_parquet(args.output)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
