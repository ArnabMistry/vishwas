"""VISHWAS Phase 3: Real-Data Product Integration — D2–D9 GeoJSON Export Pipeline.

Generates:
  backend/data/real/api_output/real_grid_D2.geojson
  backend/data/real/api_output/real_grid_D3.geojson
  backend/data/real/api_output/real_grid_D4.geojson
  backend/data/real/api_output/real_grid_D5.geojson
  backend/data/real/api_output/real_grid_D6.geojson
  backend/data/real/api_output/real_grid_D7.geojson
  backend/data/real/api_output/real_grid_D8.geojson
  backend/data/real/api_output/real_grid_D9.geojson

Methodology follows the exact Phase 2A validated evaluation specifications:
- Source: backend/data/real/features/august_2023_d2_d9.parquet
- Target evaluation date: 2023-08-28 (synchronous with Phase 1A / D1 export)
- 7 ML Predictors: f_apcp_24h, f_cape, f_hgt_500, f_u_850, f_v_850, lat, lon
- Target: error_abs = |f_apcp_24h - o_rain_24h|
- XGBoost Regressor (100 trees, max_depth=5, lr=0.1, random_state=42)
- Split Conformal Prediction (MAPIE SplitConformalRegressor, nominal 80% coverage)
- TreeSHAP physical feature attribution (top 2 drivers)
- D10 is strictly withheld in accordance with Phase 2A/2B empirical findings.
"""

import os
import sys
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb
from mapie.regression import SplitConformalRegressor
import shap

# Safe stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

FEATURE_COLS = [
    "f_apcp_24h",
    "f_cape",
    "f_hgt_500",
    "f_u_850",
    "f_v_850",
    "lat",
    "lon",
]
TARGET_COL = "error_abs"

XGB_PARAMS = {
    "n_estimators": 100,
    "max_depth": 5,
    "learning_rate": 0.1,
    "random_state": 42,
    "tree_method": "hist",
}

SHAP_TRANSLATIONS = {
    "f_cape": {
        "pos": "Elevated convective available potential energy is model-attributed to higher predicted forecast error.",
        "neg": "Thermodynamic stability associates with lower predicted forecast error."
    },
    "f_apcp_24h": {
        "pos": "Heavy precipitation forecast magnitude correlates with increased predicted uncertainty.",
        "neg": "Subtle precipitation forecast profile aligns with lower predicted error."
    },
    "f_hgt_500": {
        "pos": "500-hPa geopotential height anomaly contributes to higher model-attributed error.",
        "neg": "Mid-tropospheric geopotential height profile associates with lower predicted error."
    },
    "f_u_850": {
        "pos": "Zonal low-level wind component contributes to increased predicted forecast error.",
        "neg": "Zonal low-level flow structure aligns with lower predicted forecast error."
    },
    "f_v_850": {
        "pos": "Meridional low-level wind component contributes to higher predicted forecast error.",
        "neg": "Meridional low-level flow profile aligns with lower predicted forecast error."
    },
    "lat": {
        "pos": "Latitudinal spatial location attributes to regional baseline forecast uncertainty.",
        "neg": "Latitudinal spatial location attributes to regional baseline forecast uncertainty."
    },
    "lon": {
        "pos": "Longitudinal spatial location attributes to regional baseline forecast uncertainty.",
        "neg": "Longitudinal spatial location attributes to regional baseline forecast uncertainty."
    }
}

def get_region_name(lat: float, lon: float) -> str:
    """Assign intuitive regional meteorological basin name from geographic coordinates."""
    if lat >= 28.0:
        return "North Continental Plain & Himalayan Foothills"
    elif lat >= 22.0:
        if lon <= 75.0:
            return "Northwest Arid / Rajasthan Basin"
        elif lon <= 83.0:
            return "Central India Plateaus"
        else:
            return "East India & Gangetic Delta"
    elif lat >= 16.0:
        if lon <= 75.5:
            return "Konkan Coast & Western Ghats"
        elif lon <= 82.5:
            return "Deccan Plateau & Telangana"
        else:
            return "Odisha Coastal Plain & Offshore"
    else:
        if lon <= 77.0:
            return "Malabar Coast & Nilgiris"
        else:
            return "Peninsular South & Coromandel Coast"


def export_single_lead(
    sub_df: pd.DataFrame,
    lead: int,
    target_date: str = "2023-08-28",
    output_dir: Path = Path("backend/data/real/api_output"),
) -> Path:
    """Train lead-specific model, conformalize, compute SHAP, and export GeoJSON."""
    t0 = time.time()
    lead_hours = lead * 24
    lead_str = f"D+{lead}"

    train_df = sub_df[sub_df["init_time"] <= "2023-08-20"].copy()
    calib_df = sub_df[(sub_df["init_time"] >= "2023-08-21") & (sub_df["init_time"] <= "2023-08-25")].copy()
    target_df = sub_df[sub_df["valid_time"] == target_date].copy().reset_index(drop=True)

    if len(target_df) == 0:
        raise ValueError(f"Target date {target_date} not found for lead {lead}!")

    # Reference initialization time
    # e.g. for D2 (48h), init is 2 days prior: 2023-08-26 00:00 UTC
    target_ts = pd.Timestamp(target_date)
    ref_ts = target_ts - pd.Timedelta(days=lead)
    ref_time_str = f"{ref_ts:%Y-%m-%d} 00:00 UTC"
    valid_time_str = f"{target_date} 08:30 IST / 03:00 UTC"

    # 1. Fit XGBoost
    X_train = train_df[FEATURE_COLS]
    y_train = train_df[TARGET_COL].values
    model = xgb.XGBRegressor(**XGB_PARAMS)
    model.fit(X_train, y_train)

    # 2. Conformalize SplitConformalRegressor
    X_calib = calib_df[FEATURE_COLS]
    y_calib = calib_df[TARGET_COL].values
    conformal_reg = SplitConformalRegressor(estimator=model, confidence_level=0.80, prefit=True)
    conformal_reg.conformalize(X_calib, y_calib)

    # 3. Predict on target date
    X_target = target_df[FEATURE_COLS]
    pred_raw, intervals = conformal_reg.predict_interval(X_target)
    pred_error = np.maximum(pred_raw, 0.0)
    cqr_lower = np.maximum(intervals[:, 0, 0], 0.0)
    cqr_upper = intervals[:, 1, 0]
    interval_width = cqr_upper - cqr_lower

    # Derived bust risk score (continuous heuristic score in [0.01, 0.98])
    risk_score = np.clip(
        (pred_error / 35.0) + np.where(cqr_upper > 25.0, 0.15, 0.0),
        0.01,
        0.98
    )

    # Forecast Confidence Index (FCI) derived inversely from conformal interval width
    fci_score = np.clip(100.0 - (interval_width / 22.0) * 85.0, 5.0, 96.0)

    # 4. TreeSHAP explanations
    explainer = shap.TreeExplainer(model)
    shap_matrix = explainer.shap_values(X_target)

    # 5. Build GeoJSON features
    features = []
    half_grid = 0.125

    for i, row in target_df.iterrows():
        lat = float(row["lat"])
        lon = float(row["lon"])
        f_precip = float(row["f_apcp_24h"])
        o_rain = float(row["o_rain_24h"])
        cape_val = float(row["f_cape"])

        pe = round(float(pred_error[i]), 2)
        cl = round(float(cqr_lower[i]), 2)
        cu = round(float(cqr_upper[i]), 2)
        iw = round(float(interval_width[i]), 2)
        brs = round(float(risk_score[i]), 3)
        fci_val = round(float(fci_score[i]), 1)

        # Top 2 SHAP drivers
        sample_shap = shap_matrix[i]
        top_indices = np.argsort(np.abs(sample_shap))[::-1][:2]

        shap_drivers = []
        shap_values_list = []
        for idx in top_indices:
            feat_name = FEATURE_COLS[idx]
            s_val = float(sample_shap[idx])
            rule = SHAP_TRANSLATIONS.get(feat_name, {})
            text = rule.get("pos" if s_val >= 0 else "neg", f"{feat_name} attributes to forecast uncertainty.")
            shap_drivers.append(text)
            shap_values_list.append({
                "feature": feat_name,
                "value": round(s_val, 4),
                "impact": "Increase Error" if s_val >= 0 else "Decrease Error"
            })

        region_name = get_region_name(lat, lon)
        grid_id = f"real_grid_{lon:.2f}_{lat:.2f}"

        poly_coords = [[
            [round(lon - half_grid, 4), round(lat - half_grid, 4)],
            [round(lon + half_grid, 4), round(lat - half_grid, 4)],
            [round(lon + half_grid, 4), round(lat + half_grid, 4)],
            [round(lon - half_grid, 4), round(lat + half_grid, 4)],
            [round(lon - half_grid, 4), round(lat - half_grid, 4)]
        ]]

        hgt_500_val = float(row["f_hgt_500"])
        scaled_z500 = round(hgt_500_val / 100.0, 1)
        spread_proxy_val = round(iw / 4.0, 2)

        feature_dict = {
            "type": "Feature",
            "id": grid_id,
            "geometry": {
                "type": "Polygon",
                "coordinates": poly_coords
            },
            "properties": {
                "grid_id": grid_id,
                "lon": lon,
                "lat": lat,
                "valid_time": target_date,
                "lead_time": lead,
                "lead_time_str": lead_str,
                "lead_time_hours": lead_hours,
                "region_name": region_name,
                "f_precip": round(f_precip, 2),
                "o_rain_24h": round(o_rain, 2),
                "predicted_error": pe,
                "expected_error_median": pe,
                # Split conformal prediction bounds
                "cqr_lower": cl,
                "cqr_upper": cu,
                "cqr_bounds": f"+{cl:.1f}mm to +{cu:.1f}mm",
                "interval_width": iw,
                "bust_risk_score": brs,
                "bust_prob": brs,  # Legacy alias
                "fci": fci_val,
                "cape": round(cape_val, 1),
                "ensemble_spread": spread_proxy_val,
                "ensemble_spread_proxy": spread_proxy_val,
                "ensemble_spread_is_proxy": True,
                "z500_gradient": scaled_z500,
                "z500_height_scaled": scaled_z500,
                "wind_shear": round(float(np.sqrt(row["f_u_850"]**2 + row["f_v_850"]**2)), 1),
                "fss_horizon_day": 8,
                "fss_horizon_is_proxy": True,
                "shap_drivers": shap_drivers,
                "shap_values": shap_values_list
            }
        }
        features.append(feature_dict)

    geojson_data = {
        "type": "FeatureCollection",
        "properties": {
            "mode": "REAL",
            "model": "NOAA-GFS-0.25deg (Real Data Evaluation - Open NWP Proxy)",
            "observation_source": "IMD Gridded Daily Rainfall (Real)",
            "reference_time": ref_time_str,
            "valid_time": valid_time_str,
            "lead_time": lead,
            "lead_time_str": lead_str,
            "lead_time_hours": lead_hours,
            "total_grid_cells": len(features),
            "scientific_disclaimer": (
                f"Real-data medium-range validation for {lead_str} (+{lead_hours}h) using NOAA GFS 0.25° as an open NWP proxy "
                "and IMD gridded daily rainfall observations. Derived bust_risk_score represents a model-based risk indicator, "
                "NOT a calibrated probability. Uncertainty bounds represent Split Conformal Prediction intervals "
                "(nominal 80% coverage under exchangeability)."
            )
        },
        "features": features
    }

    out_file = output_dir / f"real_grid_D{lead}.geojson"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f, separators=(",", ":"))

    print(f"[{lead_str}] Generated {len(features):,} features -> {out_file} ({out_file.stat().st_size / 1024 / 1024:.2f} MB) in {time.time() - t0:.2f}s")
    return out_file


def main():
    matrix_path = Path("backend/data/real/features/august_2023_d2_d9.parquet")
    output_dir = Path("backend/data/real/api_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[EXPORT] Loading multi-lead matrix: {matrix_path}")
    df = pd.read_parquet(matrix_path)
    df["valid_time"] = df["valid_time"].dt.strftime("%Y-%m-%d")

    target_date = "2023-08-28"

    for lead in range(2, 10):
        sub_df = df[df["lead_day"] == lead]
        export_single_lead(sub_df, lead, target_date=target_date, output_dir=output_dir)

    print("\n[EXPORT] All D2–D9 real-data GeoJSON exports completed successfully.")


if __name__ == "__main__":
    main()
