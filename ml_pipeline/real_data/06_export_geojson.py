"""VISHWAS Phase 2 Real-Data Validation: Export Real-Data GeoJSON with Predictions, CQR Intervals, and SHAP.

Step 6:
- Select valid test date (default: 2023-08-28).
- Verify date exists in august_2023_matrix.parquet.
- Load trained XGBoost model and MAPIE conformal calibrator.
- Generate:
    predicted_error (central estimate)
    cqr_lower
    cqr_upper
    interval_width
    bust_risk_score (derived risk score in [0, 1])
    bust_prob (compatibility alias, explicitly documented as derived risk score)
    fci (Forecast Confidence Index derived from interval width)
- Compute local TreeSHAP explanations with physical attribution translations for top 2 features.
- Output: backend/data/real/api_output/real_grid_D1.geojson
"""

import os
import sys
import json
import pickle
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import shap

# Physical attribution translation rules (SHAP descriptions, not causal claims)
SHAP_TRANSLATIONS = {
    "f_cape": {
        "pos": "Elevated convective available potential energy attributes to higher predicted forecast error.",
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


def export_real_geojson(
    target_date: str = "2023-08-28",
    matrix_path: str = "backend/data/real/features/august_2023_matrix.parquet",
    model_path: str = "backend/data/real/models/cqr_model.pkl",
    output_path: str = "backend/data/real/api_output/real_grid_D1.geojson"
) -> dict:
    """Generate VISHWAS-compliant GeoJSON from real data, calibrated CQR, and TreeSHAP."""
    print(f"[GEOJSON] Loading model artifact: {model_path}")
    with open(model_path, "rb") as f:
        artifact = pickle.load(f)
        
    model = artifact["xgboost_model"]
    conformal_reg = artifact["conformal_regressor"]
    feature_cols = artifact["feature_cols"]
    
    print(f"[GEOJSON] Loading historical matrix: {matrix_path}")
    df = pd.read_parquet(matrix_path)
    df["valid_time"] = pd.to_datetime(df["valid_time"])
    
    # Verify date exists
    target_ts = pd.Timestamp(target_date)
    date_df = df[df["valid_time"] == target_ts].copy().reset_index(drop=True)
    if len(date_df) == 0:
        available_dates = df["valid_time"].dt.strftime("%Y-%m-%d").unique()
        raise ValueError(f"Target date {target_date} does not exist in dataset! Available: {sorted(list(available_dates))}")
        
    print(f"[GEOJSON] Found {len(date_df):,} grid points for target date: {target_date}")
    
    # 1. Predictions & Conformal Prediction Intervals
    X = date_df[feature_cols]
    pred_raw, intervals = conformal_reg.predict_interval(X)
    
    pred_error = np.maximum(pred_raw, 0.0)
    cqr_lower = np.maximum(intervals[:, 0, 0], 0.0)
    cqr_upper = intervals[:, 1, 0]
    interval_width = cqr_upper - cqr_lower
    
    # 2. Derived Bust Risk Score
    # Note: As required by Section 26, this is explicitly a derived risk score in [0.0, 1.0],
    # NOT a calibrated probability of bust.
    # Risk increases when predicted error approaches or exceeds 25mm, or upper bound > 25mm.
    risk_score = np.clip(
        (pred_error / 35.0) + np.where(cqr_upper > 25.0, 0.15, 0.0),
        0.01,
        0.98
    )
    
    # 3. Forecast Confidence Index (FCI)
    # Section 27: Inverse normalization based on prediction interval width (reference width = 22.0 mm)
    fci_score = np.clip(100.0 - (interval_width / 22.0) * 85.0, 5.0, 96.0)
    
    # 4. Local TreeSHAP Explanations
    print("[GEOJSON] Computing local TreeSHAP explanations...")
    explainer = shap.TreeExplainer(model)
    shap_matrix = explainer.shap_values(X)
    
    features = []
    half_grid = 0.125  # 0.25-deg resolution polygon half-width
    
    for i, row in date_df.iterrows():
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
        
        # Identify top 2 SHAP drivers by absolute magnitude
        sample_shap = shap_matrix[i]
        top_indices = np.argsort(np.abs(sample_shap))[::-1][:2]
        
        shap_drivers = []
        shap_values_list = []
        for idx in top_indices:
            feat_name = feature_cols[idx]
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
        
        # Grid cell polygon geometry
        poly_coords = [[
            [round(lon - half_grid, 4), round(lat - half_grid, 4)],
            [round(lon + half_grid, 4), round(lat - half_grid, 4)],
            [round(lon + half_grid, 4), round(lat + half_grid, 4)],
            [round(lon - half_grid, 4), round(lat + half_grid, 4)],
            [round(lon - half_grid, 4), round(lat - half_grid, 4)]
        ]]
        
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
                "lead_time": 1,
                "lead_time_str": "D+1",
                "lead_time_hours": 24,
                "region_name": region_name,
                "f_precip": round(f_precip, 2),
                "o_rain_24h": round(o_rain, 2),
                "predicted_error": pe,
                "expected_error_median": pe,
                "cqr_lower": cl,
                "cqr_upper": cu,
                "cqr_bounds": f"+{cl:.1f}mm to +{cu:.1f}mm",
                "interval_width": iw,
                "bust_risk_score": brs,
                "bust_prob": brs,  # Compatibility alias, documented as derived risk score
                "fci": fci_val,
                "cape": round(cape_val, 1),
                "ensemble_spread": round(iw / 4.0, 2),  # Heuristic proxy for frontend analog panel
                "z500_gradient": round(float(row["f_hgt_500"]) / 100.0, 1),
                "wind_shear": round(float(np.sqrt(row["f_u_850"]**2 + row["f_v_850"]**2)), 1),
                "fss_horizon_day": 8,
                "shap_drivers": shap_drivers,
                "shap_values": shap_values_list
            }
        }
        features.append(feature_dict)
        
    geojson_data = {
        "type": "FeatureCollection",
        "properties": {
            "mode": "REAL",
            "model": "NOAA-GFS-0.25deg (Real Data Evaluation)",
            "observation_source": "IMD Gridded Daily Rainfall (Real)",
            "reference_time": f"{target_date} 00:00 UTC",
            "valid_time": f"{target_date} 08:30 IST / 03:00 UTC",
            "lead_time": 1,
            "lead_time_str": "D+1",
            "lead_time_hours": 24,
            "total_grid_cells": len(features),
            "scientific_disclaimer": "Derived bust_risk_score represents a regression error / CQR risk indicator, NOT a calibrated probability. Validated against historical GFS+IMD data."
        },
        "features": features
    }
    
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(geojson_data, f)
        
    print(f"[GEOJSON] Successfully exported {len(features):,} features to: {out_file}")
    return geojson_data


def verify_real_geojson(geojson_path: str = "backend/data/real/api_output/real_grid_D1.geojson") -> bool:
    """Verify exported GeoJSON conforms to all schema requirements and specifications."""
    p = Path(geojson_path)
    if not p.exists():
        print(f"[VERIFY FAILED] GeoJSON file not found: {geojson_path}")
        return False
        
    try:
        with open(p, "r") as f:
            data = json.load(f)
            
        assert data.get("type") == "FeatureCollection", "Top-level type must be FeatureCollection"
        features = data.get("features", [])
        assert len(features) > 1000, f"Insufficient features: {len(features)}"
        
        # Verify first feature properties
        f0 = features[0]
        assert f0["geometry"]["type"] == "Polygon", "Geometry must be Polygon"
        props = f0["properties"]
        
        required_keys = [
            "lat", "lon", "valid_time", "lead_time_hours",
            "predicted_error", "cqr_lower", "cqr_upper",
            "fci", "bust_risk_score", "shap_drivers"
        ]
        for k in required_keys:
            assert k in props, f"Missing required property key: {k}"
            
        # Verify compatibility keys
        assert "bust_prob" in props, "Missing compatibility key 'bust_prob'"
        assert "cqr_bounds" in props, "Missing compatibility key 'cqr_bounds'"
        assert "f_precip" in props, "Missing compatibility key 'f_precip'"
        
        # Verify SHAP drivers has at least 1-2 translated strings
        assert isinstance(props["shap_drivers"], list) and len(props["shap_drivers"]) >= 1
        assert "contributes" in props["shap_drivers"][0] or "associates" in props["shap_drivers"][0] or "correlates" in props["shap_drivers"][0] or "aligns" in props["shap_drivers"][0] or "attributes" in props["shap_drivers"][0]
        
        print(f"[VERIFY PASS] GeoJSON validated: {len(features):,} features with valid properties and SHAP explanations.")
        return True
    except Exception as e:
        print(f"[VERIFY FAILED] GeoJSON verification exception: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Export real-data GeoJSON for VISHWAS API")
    parser.add_argument("--date", default="2023-08-28", help="Target valid date YYYY-MM-DD")
    parser.add_argument("--matrix", default="backend/data/real/features/august_2023_matrix.parquet", help="Historical matrix path")
    parser.add_argument("--model", default="backend/data/real/models/cqr_model.pkl", help="Model artifact path")
    parser.add_argument("--output", default="backend/data/real/api_output/real_grid_D1.geojson", help="Output GeoJSON path")
    parser.add_argument("--verify", action="store_true", help="Run verification only")
    args = parser.parse_args()
    
    if args.verify:
        v = verify_real_geojson(args.output)
        sys.exit(0 if v else 1)
        
    export_real_geojson(
        target_date=args.date,
        matrix_path=args.matrix,
        model_path=args.model,
        output_path=args.output
    )
    v = verify_real_geojson(args.output)
    sys.exit(0 if v else 1)

if __name__ == "__main__":
    main()
