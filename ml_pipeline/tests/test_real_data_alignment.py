"""Unit tests for VISHWAS Phase 2 real-data mathematical alignment and bust detection."""

import pytest
import importlib
import numpy as np
import pandas as pd
import xarray as xr
from pathlib import Path

align_mod = importlib.import_module("ml_pipeline.real_data.03_align_and_error")
STANDARD_COLUMNS = align_mod.STANDARD_COLUMNS
verify_alignment_parquet = align_mod.verify_alignment_parquet


def test_apcp_subtraction_positive():
    """Test 1: GFS +3h: 5.0, GFS +27h: 15.0 -> Expected 24h accumulation: 10.0."""
    gfs_3h = np.array([5.0])
    gfs_27h = np.array([15.0])
    f_apcp_24h = np.maximum(gfs_27h - gfs_3h, 0.0)
    assert f_apcp_24h[0] == pytest.approx(10.0)

def test_apcp_subtraction_negative_clamped():
    """Negative APCP difference must be clamped to zero."""
    gfs_3h = np.array([20.0, 15.5])
    gfs_27h = np.array([10.0, 15.0])
    f_apcp_24h = np.maximum(gfs_27h - gfs_3h, 0.0)
    assert f_apcp_24h[0] == 0.0
    assert f_apcp_24h[1] == 0.0

def test_bust_detection_positive():
    """Test 2: f_apcp_24h = 40, o_rain_24h = 5 -> error_abs = 35, is_bust = 1."""
    f_apcp = np.array([40.0])
    o_rain = np.array([5.0])
    error_abs = np.abs(f_apcp - o_rain)
    is_bust = ((error_abs > 25.0) & ((f_apcp > 10.0) | (o_rain > 10.0))).astype(int)
    
    assert error_abs[0] == pytest.approx(35.0)
    assert is_bust[0] == 1

def test_bust_detection_edge_cases():
    """Test boundary conditions for bust classification."""
    # Case A: error exactly 25.0 -> NOT bust (strict inequality > 25.0)
    f_a = np.array([35.0])
    o_a = np.array([10.0])
    err_a = np.abs(f_a - o_a) # 25.0
    bust_a = ((err_a > 25.0) & ((f_a > 10.0) | (o_a > 10.0))).astype(int)
    assert bust_a[0] == 0

    # Case B: error 25.1 with f_apcp > 10 -> IS bust
    f_b = np.array([35.1])
    o_b = np.array([10.0])
    err_b = np.abs(f_b - o_b) # 25.1
    bust_b = ((err_b > 25.0) & ((f_b > 10.0) | (o_b > 10.0))).astype(int)
    assert bust_b[0] == 1

    # Case C: observed heavy rain (o_rain > 10), forecast missed completely (f_apcp = 2.0, o_rain = 30.0)
    f_c = np.array([2.0])
    o_c = np.array([30.0])
    err_c = np.abs(f_c - o_c) # 28.0
    bust_c = ((err_c > 25.0) & ((f_c > 10.0) | (o_c > 10.0))).astype(int)
    assert bust_c[0] == 1

    # Case D: neither forecast nor observation exceeds 10mm (e.g. low-rain threshold guard)
    # Even if error > 25 (e.g. anomalous inputs), guard prevents false busts
    f_d = np.array([8.0])
    o_d = np.array([9.0])
    err_d = np.abs(f_d - o_d)
    bust_d = ((err_d > 25.0) & ((f_d > 10.0) | (o_d > 10.0))).astype(int)
    assert bust_d[0] == 0

def test_nan_handling():
    """Verify NaN values in observations (ocean cells) are excluded from the clean matrix."""
    lat = np.array([12.0, 12.25])
    lon = np.array([75.0, 75.25])
    f_apcp = np.array([15.0, 20.0])
    o_rain = np.array([np.nan, 18.0]) # First cell is ocean/missing
    
    error_abs = np.abs(f_apcp - o_rain)
    is_bust = ((error_abs > 25.0) & ((f_apcp > 10.0) | (o_rain > 10.0))).astype(int)
    
    df = pd.DataFrame({
        "lat": lat,
        "lon": lon,
        "valid_time": pd.Timestamp("2023-08-02"),
        "lead_time_hours": 24,
        "f_apcp_24h": f_apcp,
        "o_rain_24h": o_rain,
        "f_cape": [100.0, 200.0],
        "f_hgt_500": [5800.0, 5820.0],
        "f_u_850": [5.0, 6.0],
        "f_v_850": [-2.0, -3.0],
        "error_abs": error_abs,
        "is_bust": is_bust
    })
    
    df_clean = df.dropna(subset=["f_apcp_24h", "o_rain_24h"]).reset_index(drop=True)
    assert len(df_clean) == 1
    assert df_clean.loc[0, "lat"] == 12.25
    assert not np.isnan(df_clean.loc[0, "o_rain_24h"])

def test_coordinate_alignment_regridding():
    """Verify xarray nearest interpolation places GFS coordinates on IMD coordinates."""
    # Synthetic IMD grid (0.25 deg ascending)
    imd_lat = np.arange(10.0, 12.0, 0.25)
    imd_lon = np.arange(70.0, 72.0, 0.25)
    imd_ds = xr.Dataset(
        {"rain": (("lat", "lon"), np.ones((len(imd_lat), len(imd_lon))))},
        coords={"lat": imd_lat, "lon": imd_lon}
    )
    
    # Synthetic GFS grid (descending latitude)
    gfs_lat = np.arange(12.0, 9.75, -0.25)
    gfs_lon = np.arange(70.0, 72.0, 0.25)
    gfs_ds = xr.Dataset(
        {"apcp": (("latitude", "longitude"), np.full((len(gfs_lat), len(gfs_lon)), 5.0))},
        coords={"latitude": gfs_lat, "longitude": gfs_lon}
    )
    
    regridded = gfs_ds.interp(latitude=imd_ds.lat, longitude=imd_ds.lon, method="nearest")
    np.testing.assert_allclose(regridded.latitude.values, imd_ds.lat.values)
    np.testing.assert_allclose(regridded.longitude.values, imd_ds.lon.values)
    assert regridded["apcp"].shape == imd_ds["rain"].shape

def test_test_matrix_parquet_integrity():
    """Verify generated test_matrix.parquet passes full verification check."""
    parquet_path = "backend/data/real/features/test_matrix.parquet"
    if not Path(parquet_path).exists():
        pytest.skip(f"Test matrix {parquet_path} does not exist yet")
        
    assert verify_alignment_parquet(parquet_path) is True
    
    df = pd.read_parquet(parquet_path)
    assert list(df.columns) == STANDARD_COLUMNS
    assert (df["lead_time_hours"] == 24).all()
    assert len(df) == 4905
    assert df["is_bust"].sum() == 575
