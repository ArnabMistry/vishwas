"""
backend/main.py
VISHWAS - Weather Intelligence & Spatiotemporal Hazard Warning Assessment System
FastAPI Backend API Serving Gridded Reliability Predictions, CQR Bounds, & Translated XAI.
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import os
import json
import math

app = FastAPI(
    title="VISHWAS API - Forecast Reliability Engine",
    description="Operational reliability monitoring and Conformalized Quantile Regression bust detection for NCMRWF NCUM-G forecasts.",
    version="1.0.0"
)

# Enable CORS for localhost:3000 and any client origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# In-memory cache for grids 1-10 for sub-millisecond serving
GRIDS_CACHE: Dict[int, Dict[str, Any]] = {}

def get_grid_data(lead_time: int) -> Dict[str, Any]:
    if lead_time not in GRIDS_CACHE:
        filepath = os.path.join(DATA_DIR, f"grid_{lead_time}.geojson")
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail=f"Forecast grid for lead time D+{lead_time} not found.")
        with open(filepath, "r", encoding="utf-8") as f:
            GRIDS_CACHE[lead_time] = json.load(f)
    return GRIDS_CACHE[lead_time]

# Preload grids
@app.on_event("startup")
def preload_data():
    for lt in range(1, 11):
        try:
            get_grid_data(lt)
        except Exception as e:
            print(f"Warning: Failed to preload grid_{lt}.geojson: {e}")

# Models
class SystemStatus(BaseModel):
    status: str
    nwp_model: str
    horizontal_resolution: str
    vertical_levels: int
    cycle: str
    data_provenance: str
    ml_regressor: str
    calibration_method: str
    confidence_level: str
    mean_network_fci: float
    high_risk_cells_count: int
    telemetry_status: str

class AlertZone(BaseModel):
    id: str
    region_name: str
    lead_time: int
    lead_time_str: str
    lat: float
    lon: float
    bust_prob: float
    fci: float
    cqr_bounds: str
    primary_driver: str
    dna_barcode: List[float] # D+1 to D+10 bust probabilities

class PointExplanation(BaseModel):
    lat: float
    lon: float
    lead_time: int
    lead_time_str: str
    region_name: str
    fci: float
    bust_prob: float
    cqr_bounds: str
    primary_driver: str
    secondary_driver: str
    tertiary_driver: str
    physical_narrative: str
    shap_contributions: List[Dict[str, Any]]

@app.get("/")
def root():
    return {
        "engine": "VISHWAS - Forecast Reliability Engine",
        "agency": "MoES / NCMRWF Unified Model Verification System",
        "docs_url": "/docs",
        "version": "1.0.0"
    }

@app.get("/healthz")
def healthz():
    return {"status": "ok", "telemetry": "CONNECTED"}

@app.get("/api/v1/status", response_model=SystemStatus)
def get_system_status():
    grid_d1 = get_grid_data(1)
    features = grid_d1.get("features", [])
    fcis = [f["properties"]["fci"] for f in features]
    high_risks = [f for f in features if f["properties"]["bust_prob"] > 0.70]

    mean_fci = round(sum(fcis) / max(1, len(fcis)), 1)

    return SystemStatus(
        status="OPERATIONAL",
        nwp_model="NCUM-G",
        horizontal_resolution="12 km",
        vertical_levels=70,
        cycle="00Z Operational Assimilation",
        data_provenance="NCMRWF Global Stream / IMD High-Res Proxy",
        ml_regressor="XGBoost Regressor v1.2",
        calibration_method="Conformalized Quantile Regression (CQR)",
        confidence_level="80% (alpha=0.20)",
        mean_network_fci=mean_fci,
        high_risk_cells_count=len(high_risks),
        telemetry_status="STABLE"
    )

@app.get("/api/v1/forecast/grid")
def get_forecast_grid(lead_time: int = Query(1, ge=1, le=10, description="Lead time in days (1 to 10)")):
    """Returns the full GeoJSON FeatureCollection for the selected lead time."""
    return get_grid_data(lead_time)

@app.get("/api/v1/forecast/point")
def get_forecast_point(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    lead_time: int = Query(1, ge=1, le=10, description="Lead time in days")
):
    """
    Finds the nearest grid cell to the specified lat/lon and provides
    time-series evolution, CQR bounds, FSS decay curve, and historical analogs.
    """
    grid = get_grid_data(lead_time)
    features = grid.get("features", [])

    # Find closest grid feature
    best_dist = float("inf")
    matched_feature = None

    for f in features:
        props = f["properties"]
        d = math.hypot(props["lat"] - lat, props["lon"] - lon)
        if d < best_dist:
            best_dist = d
            matched_feature = f

    if not matched_feature:
        raise HTTPException(status_code=404, detail="Coordinate out of spatial bounds.")

    m_props = matched_feature["properties"]
    m_lat = m_props["lat"]
    m_lon = m_props["lon"]

    # Gather full 10-day time-series for this exact cell
    time_series = []
    for lt in range(1, 11):
        g = get_grid_data(lt)
        for cf in g["features"]:
            cp = cf["properties"]
            if cp["lat"] == m_lat and cp["lon"] == m_lon:
                time_series.append({
                    "day": f"D+{lt}",
                    "lead_time": lt,
                    "f_precip": cp["f_precip"],
                    "bust_prob": cp["bust_prob"],
                    "fci": cp["fci"],
                    "cqr_lower": cp["cqr_lower"],
                    "cqr_upper": cp["cqr_upper"],
                    "cqr_bounds": cp["cqr_bounds"],
                    "ensemble_spread": cp["ensemble_spread"],
                    "cape": cp["cape"]
                })
                break

    # Historical analogs
    analogs = [
        {
            "event_name": "2020 Bay of Bengal Monsoon Low (BOB-02)",
            "date": "August 18, 2020",
            "synoptic_similarity": 94.2,
            "observed_error": "+52.4 mm (Dry NWP bias)",
            "outcome": "Model under-forecast inland precipitation peak by 48%"
        },
        {
            "event_name": "2019 Cyclone Fani Outer Convective Band",
            "date": "May 2, 2019",
            "synoptic_similarity": 88.7,
            "observed_error": "+38.6 mm (Track offset)",
            "outcome": "Coastal precipitation axis displaced 65 km eastward in D+4"
        },
        {
            "event_name": "2021 Deep Depression 03B",
            "date": "September 12, 2021",
            "synoptic_similarity": 82.5,
            "observed_error": "+44.1 mm",
            "outcome": "Extreme rain burst over coastal plains missed by deterministic NCUM"
        }
    ]

    return {
        "selected_coordinate": {"lat": lat, "lon": lon},
        "matched_cell": {
            "grid_id": m_props["grid_id"],
            "lat": m_lat,
            "lon": m_lon,
            "region_name": m_props["region_name"]
        },
        "current_lead_time": lead_time,
        "properties": m_props,
        "time_series": time_series,
        "fss_decay": m_props.get("fss_decay", []),
        "analogs": analogs
    }

@app.get("/api/v1/explain", response_model=PointExplanation)
def get_explanation(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    lead_time: int = Query(1, ge=1, le=10, description="Lead time in days")
):
    """
    Returns translated Linguistic TreeSHAP explanations decomposing
    the mathematical error contribution into operational meteorological physics.
    """
    grid = get_grid_data(lead_time)
    features = grid.get("features", [])

    best_dist = float("inf")
    matched_feature = None

    for f in features:
        props = f["properties"]
        d = math.hypot(props["lat"] - lat, props["lon"] - lon)
        if d < best_dist:
            best_dist = d
            matched_feature = f

    if not matched_feature:
        raise HTTPException(status_code=404, detail="Coordinate out of spatial bounds.")

    props = matched_feature["properties"]
    drivers = props.get("shap_drivers", [])
    primary = drivers[0] if len(drivers) > 0 else "Stable quasi-geostrophic balance."
    secondary = drivers[1] if len(drivers) > 1 else "Ensemble variance within normal limits."
    tertiary = drivers[2] if len(drivers) > 2 else "Thermodynamic profile aligned with climatology."

    # Construct operational meteorological narrative
    bust_prob = props["bust_prob"]
    if bust_prob > 0.80:
        narrative = (
            f"VISHWAS flags severe forecast fragility at D+{lead_time} over {props['region_name']}. "
            f"The XGBoost model, calibrated with MAPIE CQR, estimates with 80% conformal coverage that "
            f"NCUM-G will under-predict rainfall by {props['cqr_bounds']}. TreeSHAP feature attribution "
            f"reveals that anomalous CAPE ({props['cape']} J/kg) is breaking parameterized convective equilibrium, "
            f"while an extreme ensemble spread divergence ({props['ensemble_spread']} mm) indicates "
            f"severe synoptic bifurcation. Operational intervention and ensemble re-weighting are recommended."
        )
    elif bust_prob > 0.50:
        narrative = (
            f"Moderate forecast uncertainty detected at D+{lead_time} over {props['region_name']}. "
            f"The expected error interval is {props['cqr_bounds']} with an FCI of {props['fci']}/100. "
            f"Primary error contribution stems from coastal moisture flux convergence and mesoscale boundary layer gradients."
        )
    else:
        narrative = (
            f"High forecast confidence (FCI: {props['fci']}/100) at D+{lead_time} over {props['region_name']}. "
            f"NCUM-G deterministic predictions are well within the 80% conformal bounds ({props['cqr_bounds']}). "
            f"Large-scale planetary wave flow is stable."
        )

    return PointExplanation(
        lat=props["lat"],
        lon=props["lon"],
        lead_time=lead_time,
        lead_time_str=f"D+{lead_time}",
        region_name=props["region_name"],
        fci=props["fci"],
        bust_prob=props["bust_prob"],
        cqr_bounds=props["cqr_bounds"],
        primary_driver=primary,
        secondary_driver=secondary,
        tertiary_driver=tertiary,
        physical_narrative=narrative,
        shap_contributions=props.get("shap_values", [])
    )

@app.get("/api/v1/alerts", response_model=List[AlertZone])
def get_alerts():
    """
    Returns high-priority operational bust alert zones with Confidence DNA Barcodes
    (10 sequential values representing Days 1 to 10).
    """
    # Key hotspots across India for the demo scenario
    hotspots = [
        {"name": "Odisha Coastal Plain & Offshore", "lat": 20.0, "lon": 85.0, "primary_lt": 5},
        {"name": "North / Central Bay of Bengal", "lat": 18.0, "lon": 87.0, "primary_lt": 3},
        {"name": "Chhattisgarh & East MP Trough", "lat": 21.0, "lon": 82.0, "primary_lt": 7},
        {"name": "Konkan & Western Ghats Escarpment", "lat": 16.0, "lon": 74.0, "primary_lt": 4},
        {"name": "Western Himalayas Frontal Zone", "lat": 31.0, "lon": 77.0, "primary_lt": 2}
    ]

    alerts = []
    for h in hotspots:
        target_lat = h["lat"]
        target_lon = h["lon"]
        pref_lt = h["primary_lt"]

        # Calculate DNA barcode across 10 days
        dna_barcode = []
        target_props = None
        for lt in range(1, 11):
            g = get_grid_data(lt)
            best_d = float("inf")
            best_p = None
            for f in g["features"]:
                p = f["properties"]
                d = math.hypot(p["lat"] - target_lat, p["lon"] - target_lon)
                if d < best_d:
                    best_d = d
                    best_p = p
            if best_p:
                dna_barcode.append(best_p["bust_prob"])
                if lt == pref_lt:
                    target_props = best_p

        if target_props:
            alerts.append(AlertZone(
                id=f"alert_{int(target_lon)}_{int(target_lat)}",
                region_name=h["name"],
                lead_time=pref_lt,
                lead_time_str=f"D+{pref_lt}",
                lat=target_lat,
                lon=target_lon,
                bust_prob=target_props["bust_prob"],
                fci=target_props["fci"],
                cqr_bounds=target_props["cqr_bounds"],
                primary_driver=target_props["shap_drivers"][0] if target_props["shap_drivers"] else "Synoptic instability",
                dna_barcode=dna_barcode
            ))

    # Sort alerts by bust_prob descending
    alerts.sort(key=lambda x: x.bust_prob, reverse=True)
    return alerts

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
