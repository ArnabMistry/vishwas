// frontend/types/forecast.ts

export interface GridProperties {
  grid_id: string;
  lon: number;
  lat: number;
  lead_time: number;
  lead_time_str: string;
  region_name: string;
  f_precip: number;
  bust_prob: number;
  fci: number;
  cqr_bounds: string;
  cqr_lower: number;
  cqr_upper: number;
  expected_error_median: number;
  interval_width: number;
  cape: number;
  ensemble_spread: number;
  z500_gradient: number;
  wind_shear: number;
  fss_horizon_day: number;
  shap_drivers: string[];
  shap_values?: Array<{ feature: string; value: number; impact: string }>;
  fss_decay?: Array<{ day: string; fss: number; threshold: number }>;
}

export interface GridFeature {
  type: "Feature";
  id: string;
  geometry: {
    type: "Polygon";
    coordinates: number[][][];
  };
  properties: GridProperties;
}

export interface ForecastGridGeoJSON {
  type: "FeatureCollection";
  properties: {
    lead_time: number;
    lead_time_str: string;
    model: string;
    reference_time: string;
    valid_time: string;
    total_grid_cells: number;
  };
  features: GridFeature[];
}

export interface AlertZoneItem {
  id: string;
  region_name: string;
  lead_time: number;
  lead_time_str: string;
  lat: number;
  lon: number;
  bust_prob: number;
  fci: number;
  cqr_bounds: string;
  primary_driver: string;
  dna_barcode: number[];
}

export interface SystemStatusData {
  status: string;
  nwp_model: string;
  horizontal_resolution: string;
  vertical_levels: number;
  cycle: string;
  data_provenance: string;
  ml_regressor: string;
  calibration_method: string;
  confidence_level: string;
  mean_network_fci: number;
  high_risk_cells_count: number;
  telemetry_status: string;
}

export interface PointDetailsResponse {
  selected_coordinate: { lat: number; lon: number };
  matched_cell: {
    grid_id: string;
    lat: number;
    lon: number;
    region_name: string;
  };
  current_lead_time: number;
  properties: GridProperties;
  time_series: Array<{
    day: string;
    lead_time: number;
    f_precip: number;
    bust_prob: number;
    fci: number;
    cqr_lower: number;
    cqr_upper: number;
    cqr_bounds: string;
    ensemble_spread: number;
    cape: number;
  }>;
  fss_decay: Array<{ day: string; fss: number; threshold: number }>;
  analogs: Array<{
    event_name: string;
    date: string;
    synoptic_similarity: number;
    observed_error: string;
    outcome: string;
  }>;
}
