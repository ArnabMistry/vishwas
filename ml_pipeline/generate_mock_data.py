"""
ml_pipeline/generate_mock_data.py
VISHWAS - Weather Intelligence & Spatiotemporal Hazard Warning Assessment System
Generates scientifically grounded 10-day GeoJSON forecast reliability grids
calibrated via Conformalized Quantile Regression (CQR) and Linguistic TreeSHAP.
"""

import json
import math
import os
from typing import Dict, Any, List

# Output directory for GeoJSON grids
OUTPUT_DIRS = [
    os.path.join(os.path.dirname(__file__), "..", "backend", "data"),
    os.path.join(os.path.dirname(__file__), "data"),
]

def get_region_name(lon: float, lat: float) -> str:
    """Classify lat/lon into realistic Indian meteorological sub-regions."""
    if 18.0 <= lat <= 22.5 and 83.5 <= lon <= 87.5:
        return "Odisha Coastal Plain & Offshore"
    elif 15.0 <= lat <= 21.0 and 85.0 <= lon <= 93.0:
        return "North / Central Bay of Bengal"
    elif 21.5 <= lat <= 26.0 and 86.0 <= lon <= 90.0:
        return "Gangetic West Bengal & Delta"
    elif 21.5 <= lat <= 25.5 and 82.0 <= lon <= 86.5:
        return "Chota Nagpur & Jharkhand Plateau"
    elif 20.0 <= lat <= 24.5 and 79.0 <= lon <= 83.5:
        return "Chhattisgarh & East Madhya Pradesh"
    elif 21.0 <= lat <= 26.0 and 74.0 <= lon <= 79.5:
        return "West Madhya Pradesh & Narmada Valley"
    elif 24.0 <= lat <= 30.5 and 76.0 <= lon <= 84.0:
        return "Indo-Gangetic Plains & Uttar Pradesh"
    elif 13.0 <= lat <= 19.5 and 79.0 <= lon <= 85.0:
        return "Coastal Andhra & Krishna Basin"
    elif 11.0 <= lat <= 19.0 and 73.0 <= lon <= 77.0:
        return "Konkan & Western Ghats Escarpment"
    elif 8.0 <= lat <= 13.5 and 75.0 <= lon <= 80.0:
        return "South Peninsular (TN & Kerala)"
    elif 20.0 <= lat <= 25.0 and 68.0 <= lon <= 73.5:
        return "Gujarat Plains & Saurashtra"
    elif 25.0 <= lat <= 31.0 and 69.0 <= lon <= 76.0:
        return "West Rajasthan & Thar Desert"
    elif lat > 30.0 and 74.0 <= lon <= 80.0:
        return "Western Himalayas (HP & Uttarakhand)"
    elif lat > 23.0 and lon > 89.0:
        return "Northeast & Brahmaputra Basin"
    elif lat <= 15.0 and lon > 80.0:
        return "South Bay of Bengal"
    elif lon < 73.0:
        return "East Arabian Sea Marine Basin"
    else:
        return "Central Peninsular Plateau"

def calculate_grid_cell(lon: float, lat: float, lead_time: int) -> Dict[str, Any]:
    """
    Synthesize physical and conformal reliability parameters for grid point at lead_time D+L.
    Critical Scenario:
    Moving Monsoon Depression / Tropical Disturbance:
    - Day 1: [lon: 86.5, lat: 18.5] (Offshore Bay of Bengal)
    - Day 2: [lon: 86.0, lat: 19.2]
    - Day 3: [lon: 85.5, lat: 19.8] (Approaching Puri / Paradip Coast)
    - Day 4: [lon: 85.2, lat: 20.2] (Landfall & Convective Amplification)
    - Day 5: [lon: 85.0, lat: 20.0] (Odisha Interior - SEVERE BUST PEAK)
    - Day 6: [lon: 83.8, lat: 20.8] (Moving towards Chhattisgarh)
    - Day 7: [lon: 82.5, lat: 21.5] (Central India Trough)
    - Day 8: [lon: 81.0, lat: 22.2] (East MP)
    - Day 9: [lon: 79.5, lat: 22.8] (Central MP)
    - Day 10: [lon: 78.0, lat: 23.5] (Dissipating over West MP)
    """
    # Track center per day
    storm_tracks = {
        1: (86.5, 18.5, 0.48),
        2: (86.0, 19.2, 0.62),
        3: (85.5, 19.8, 0.74),
        4: (85.2, 20.2, 0.86),
        5: (85.0, 20.0, 0.94), # Critical demo epicenter
        6: (83.8, 20.8, 0.82),
        7: (82.5, 21.5, 0.75),
        8: (81.0, 22.2, 0.68),
        9: (79.5, 22.8, 0.58),
        10: (78.0, 23.5, 0.45),
    }

    center_lon, center_lat, peak_bust = storm_tracks[lead_time]

    # Euclidean distance in degrees to storm epicenter
    dist = math.sqrt((lon - center_lon) ** 2 + (lat - center_lat) ** 2)

    # Secondary orographic feature: Western Ghats moisture convergence
    is_western_ghats = (12.0 <= lat <= 18.0) and (73.0 <= lon <= 75.5)
    ghats_dist = abs(lon - 74.0) if is_western_ghats else 99.0

    # Secondary feature: Western Himalayan frontal interaction
    is_himalayan = (lat >= 30.5) and (75.0 <= lon <= 79.5)

    # Base background noise
    bg_noise = 0.08 * math.sin(lon * 0.4 + lead_time * 0.3) + 0.05 * math.cos(lat * 0.5 - lead_time * 0.2)
    base_prob = max(0.04, min(0.25, 0.08 + (lead_time * 0.015) + bg_noise))

    # Calculate storm impact envelope
    # Sigma radius expands as lead time increases (error upscale growth)
    radius = 2.4 + (lead_time * 0.25)
    if dist < radius:
        storm_influence = math.exp(-0.5 * (dist / (radius * 0.55)) ** 2)
        bust_prob = base_prob + (peak_bust - base_prob) * storm_influence
    else:
        bust_prob = base_prob

    # Add secondary orographic effect
    if is_western_ghats:
        bust_prob = min(0.85, bust_prob + 0.28 * math.exp(-0.5 * (ghats_dist / 1.0) ** 2))
    elif is_himalayan:
        bust_prob = min(0.78, bust_prob + 0.22)

    # Ensure Day 5 Odisha epicenter satisfies strict spec requirement:
    # "CRITICAL DEMO SCENARIO: Inject a persistent, moving 'Bust Zone' starting at [lon: 85, lat: 20] (Odisha) on Day 1,
    # moving slightly NW by Day 5. In this zone, artificially force bust_prob > 0.85..."
    if lead_time == 5 and (84.0 <= lon <= 86.0) and (19.0 <= lat <= 21.0):
        bust_prob = max(0.91, bust_prob)
    elif lead_time == 4 and (84.5 <= lon <= 86.5) and (19.5 <= lat <= 21.0):
        bust_prob = max(0.87, bust_prob)
    elif lead_time == 1 and (85.5 <= lon <= 87.5) and (17.5 <= lat <= 19.5):
        bust_prob = max(0.52, bust_prob)

    bust_prob = round(max(0.02, min(0.98, bust_prob)), 3)

    # Physical meteorological variables
    if dist < radius:
        # High thermodynamic and dynamical stress
        f_precip = round(22.0 + 55.0 * math.exp(-dist / 1.8) + (lead_time * 1.5), 1)
        cape = round(2100 + 2100 * math.exp(-dist / 2.0), 0)
        ensemble_spread = round(4.5 + 8.5 * (lead_time / 10.0) * math.exp(-dist / 2.5), 1)
        z500_gradient = round(28.0 + 34.0 * math.exp(-dist / 2.2), 1)
        wind_shear = round(18.0 + 16.0 * math.exp(-dist / 2.0), 1)
    else:
        f_precip = round(max(0.0, 3.5 + 8.0 * math.sin(lon * 0.3 + lat * 0.2)), 1)
        cape = round(max(400.0, 1100.0 + 600.0 * math.cos(lat * 0.3)), 0)
        ensemble_spread = round(1.2 + 0.4 * lead_time, 1)
        z500_gradient = round(12.0 + 0.8 * lead_time, 1)
        wind_shear = round(8.0 + 1.2 * lead_time, 1)

    # Conformal Quantile Regression (CQR) bounds (alpha=0.2, 80% coverage)
    # Expected error interval: [q_0.1, q_0.9]
    # In bust zones, lower bound is elevated significantly, showing guaranteed error
    base_spread = ensemble_spread * 1.8 + (lead_time * 2.2)
    if bust_prob > 0.80:
        cqr_lower = round(max(15.0, 24.0 + (bust_prob - 0.8) * 90.0 + lead_time * 2.5), 1)
        cqr_upper = round(cqr_lower + base_spread + 18.0, 1)
        expected_median = round((cqr_lower + cqr_upper) / 2.0, 1)
    elif bust_prob > 0.50:
        cqr_lower = round(8.0 + (bust_prob - 0.5) * 35.0 + lead_time * 1.2, 1)
        cqr_upper = round(cqr_lower + base_spread + 10.0, 1)
        expected_median = round((cqr_lower + cqr_upper) / 2.0, 1)
    else:
        cqr_lower = round(max(0.5, 1.2 + lead_time * 0.5), 1)
        cqr_upper = round(cqr_lower + base_spread * 0.8 + 4.0, 1)
        expected_median = round((cqr_lower + cqr_upper) / 2.0, 1)

    # Forecast Confidence Indicator (FCI): 0 to 100
    # FCI = 100 * exp(-lambda * (cqr_upper - cqr_lower))
    interval_width = cqr_upper - cqr_lower
    fci_raw = 100.0 * math.exp(-0.048 * interval_width)
    fci = round(max(5.0, min(98.0, fci_raw)), 1)

    cqr_bounds_str = f"+{cqr_lower}mm to +{cqr_upper}mm"

    # Explainability & Linguistic TreeSHAP translation
    shap_drivers: List[str] = []
    shap_values: List[Dict[str, Any]] = []

    if bust_prob > 0.80:
        shap_drivers = [
            "Anomalous CAPE exceeding convective parameterization limits (> 3800 J/kg)",
            "Extreme ensemble divergence indicating unpredictable synoptic flow",
            "Rapidly deepening upper-level trough with intense diabatic heating feedback"
        ]
        shap_values = [
            {"feature": "CAPE Anomaly", "value": +0.38, "impact": "High Risk"},
            {"feature": "Ensemble Spread Divergence", "value": +0.31, "impact": "High Risk"},
            {"feature": "Z500 Trough Gradient", "value": +0.18, "impact": "Moderate Risk"},
            {"feature": "Vertical Wind Shear", "value": +0.08, "impact": "Low Risk"}
        ]
    elif bust_prob > 0.50:
        shap_drivers = [
            "Elevated low-level moisture convergence over coastal transition zone",
            "Moderate ensemble spread divergence along cyclonic flank",
            "Mesoscale baroclinic gradient unresolved by 12km grid"
        ]
        shap_values = [
            {"feature": "Low-level Moisture Convergence", "value": +0.24, "impact": "Moderate Risk"},
            {"feature": "Ensemble Spread Divergence", "value": +0.19, "impact": "Moderate Risk"},
            {"feature": "Baroclinic Instability", "value": +0.12, "impact": "Low Risk"},
            {"feature": "Topographic Forcing", "value": +0.06, "impact": "Low Risk"}
        ]
    else:
        shap_drivers = [
            "Synoptic flow governed by quasi-geostrophic balance",
            "Ensemble variance within climatological bounds",
            "Convective parameterization stable"
        ]
        shap_values = [
            {"feature": "Quasi-Geostrophic Balance", "value": -0.22, "impact": "Stable"},
            {"feature": "Low Ensemble Variance", "value": -0.18, "impact": "Stable"},
            {"feature": "Stable Thermodynamic Sounding", "value": -0.15, "impact": "Stable"},
            {"feature": "Zonal Flow Alignment", "value": -0.09, "impact": "Stable"}
        ]

    # Specific override for Day 5 Odisha epicenter
    if lead_time == 5 and (84.0 <= lon <= 86.0) and (19.0 <= lat <= 21.0):
        shap_drivers = [
            "Anomalous CAPE exceeding convective limits (> 3800 J/kg)",
            "Extreme ensemble divergence indicating unpredictable flow",
            "Severe diabatic heating feedback causing unresolvable track displacement"
        ]

    # Fractions Skill Score (FSS) Decay Curve (Day 1 to 10)
    # FSS degrades over lead time; threshold is 0.5
    fss_decay = []
    horizon_day = 8
    for d in range(1, 11):
        if bust_prob > 0.80:
            # Degrades quickly, crosses 0.5 at day 3 or 4
            score = max(0.12, round(0.92 - (d - 1) * 0.16 - (0.08 if d >= 4 else 0.0), 2))
            if score < 0.5 and horizon_day == 8:
                horizon_day = d
        elif bust_prob > 0.50:
            score = max(0.20, round(0.94 - (d - 1) * 0.10, 2))
            if score < 0.5 and horizon_day == 8:
                horizon_day = d
        else:
            score = max(0.42, round(0.96 - (d - 1) * 0.05, 2))
        fss_decay.append({"day": f"D+{d}", "fss": score, "threshold": 0.5})

    region_name = get_region_name(lon, lat)

    # Geometry: 1x1 degree polygon grid cell
    half = 0.5
    polygon_coords = [[
        [round(lon - half, 4), round(lat - half, 4)],
        [round(lon + half, 4), round(lat - half, 4)],
        [round(lon + half, 4), round(lat + half, 4)],
        [round(lon - half, 4), round(lat + half, 4)],
        [round(lon - half, 4), round(lat - half, 4)],
    ]]

    return {
        "type": "Feature",
        "id": f"grid_{int(lon)}_{int(lat)}",
        "geometry": {
            "type": "Polygon",
            "coordinates": polygon_coords
        },
        "properties": {
            "grid_id": f"grid_{int(lon)}_{int(lat)}",
            "lon": lon,
            "lat": lat,
            "lead_time": lead_time,
            "lead_time_str": f"D+{lead_time}",
            "region_name": region_name,
            "f_precip": f_precip,
            "bust_prob": bust_prob,
            "fci": fci,
            "cqr_bounds": cqr_bounds_str,
            "cqr_lower": cqr_lower,
            "cqr_upper": cqr_upper,
            "expected_error_median": expected_median,
            "interval_width": round(interval_width, 1),
            "cape": cape,
            "ensemble_spread": ensemble_spread,
            "z500_gradient": z500_gradient,
            "wind_shear": wind_shear,
            "fss_horizon_day": horizon_day,
            "shap_drivers": shap_drivers,
            "shap_values": shap_values,
            "fss_decay": fss_decay
        }
    }

def generate_all_grids():
    """Generate 10 GeoJSON FeatureCollections for Days 1 through 10."""
    for out_dir in OUTPUT_DIRS:
        os.makedirs(out_dir, exist_ok=True)

    lon_range = range(68, 98) # 68 to 97
    lat_range = range(8, 36)  # 8 to 35

    print(f"Generating 1x1 grid over India ({len(lon_range)} lons x {len(lat_range)} lats = {len(lon_range)*len(lat_range)} cells)...")

    for lead_time in range(1, 11):
        features = []
        for lat in lat_range:
            for lon in lon_range:
                cell = calculate_grid_cell(float(lon), float(lat), lead_time)
                features.append(cell)

        geojson = {
            "type": "FeatureCollection",
            "properties": {
                "lead_time": lead_time,
                "lead_time_str": f"D+{lead_time}",
                "model": "NCUM-G (12km, 70L)",
                "reference_time": "2026-09-30T00:00:00Z",
                "valid_time": f"2026-10-{lead_time:02d}T00:00:00Z",
                "total_grid_cells": len(features)
            },
            "features": features
        }

        for out_dir in OUTPUT_DIRS:
            filename = os.path.join(out_dir, f"grid_{lead_time}.geojson")
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(geojson, f, separators=(',', ':'))
            print(f"Saved {filename} ({os.path.getsize(filename):,} bytes)")

    print("All 10 forecast grids successfully generated.")

if __name__ == "__main__":
    generate_all_grids()
