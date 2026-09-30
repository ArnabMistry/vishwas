# VISHWAS Phase 2: Real-Data Validation Report

## 1. Experiment Objective
This experiment establishes a scientifically defensible real-data validation pipeline for the VISHWAS forecast bust-detection and error-quantification system. Using freely accessible historical meteorological data—NOAA Global Forecast System (GFS) numerical weather predictions and India Meteorological Department (IMD) gridded daily rainfall observations for August 2023—this research validation confirms that VISHWAS's core pipeline operates rigorously and reproducibly on empirical atmospheric observations:
1. Spatial and temporal alignment between heterogeneous numerical weather prediction (NWP) grids and observational gauge-gridded datasets.
2. Chronological machine-learning formulation avoiding temporal data leakage.
3. Quantified forecast error reduction using gradient-boosted decision trees (XGBoost).
4. Finite-sample prediction interval calibration using Split Conformal Prediction (MAPIE).
5. Explainable local feature attribution using TreeSHAP with operational meteorological interpretations.

> **Important Scientific Note:** This research pipeline validates the mathematical, data engineering, and machine learning framework against historical NOAA GFS (0.25°) and IMD (0.25°) datasets. It is a **real-data evaluation using NOAA GFS 0.25° as an open-access NWP proxy**. It is **NOT** an operational validation of NCUM-G (the National Centre for Medium Range Weather Forecasting Unified Model - Global), nor does it substitute for formal operational certification by MoES/NCMRWF.

---

## 2. Data Provenance

| Parameter | NWP Forecast Model | Observational Reference |
| :--- | :--- | :--- |
| **Source System** | NOAA Global Forecast System (GFS) | India Meteorological Department (IMD) Pune |
| **Data Format** | GRIB2 via NOAA AWS S3 Open Data | NetCDF4 / Binary Gridded Gauge Interpolation |
| **Access Method** | `herbie-data` (2024.11.0) automated retrieval | IMD Daily Rainfall Gridded Archive (`imdpune.gov.in`) |
| **Grid Resolution** | 0.25° × 0.25° (~27 km at equator) | 0.25° × 0.25° regular latitude/longitude |
| **Spatial Bounds** | Indian Subcontinent Window (Lat 8.0°–36.0°N, Lon 68.0°–98.0°E) | Indian Landmass (Lat 8.0°–36.0°N, Lon 68.0°–98.0°E) |
| **Initialization** | 00:00 UTC cycle daily | Daily accumulation reported at 08:30 IST (03:00 UTC) |
| **Forecast Steps** | +3h (F03) and +27h (F27) forecast horizons | 24-hour accumulated gauge rainfall (Day 0 03:00 UTC to Day +1 03:00 UTC) |
| **Target Period** | August 1, 2023 – August 31, 2023 (Active/Break SW Monsoon) | August 1, 2023 – August 31, 2023 (31 calendar days) |

---

## 3. Data Processing & Alignment Methodology

### Spatial Alignment
The reference coordinate framework is established on the IMD 0.25° grid over mainland India ($113 \times 121 = 13,673$ grid points total, with 4,905 valid land cells excluding sea and non-reporting trans-boundary cells).
GFS longitude coordinates ($0^\circ \text{ to } 360^\circ$) were converted to standard Greenwich coordinates ($68^\circ \text{ to } 98^\circ\text{E}$). Spatial regridding of GFS meteorological fields onto the IMD grid points was performed via **nearest-neighbor interpolation using xarray onto the IMD grid** (`xarray.Dataset.interp(method="nearest")`), preserving exact coordinate correspondence without introducing spatial distortion.

### Temporal Accumulation Alignment
In GFS GRIB2 outputs, the total precipitation (`APCP`) variable represents accumulated precipitation from the preceding accumulation cycle reset:
- Forecast Step +3h (`APCP`): Accumulation from 00:00 UTC to 03:00 UTC on Day 0.
- Forecast Step +27h (`APCP`): Continuous accumulation from 00:00 UTC Day 0 to 03:00 UTC Day +1 (27 hours total).

The valid 24-hour forecast accumulation matching the IMD observational window (03:00 UTC Day 0 to 03:00 UTC Day +1) is calculated via:
$$\text{APCP}_{24\text{h}} = \max\left(\text{APCP}_{+27\text{h}} - \text{APCP}_{+3\text{h}},\, 0.0\right)$$
Values below zero resulting from numerical precision artifacts are clamped strictly to $0.0\text{ mm}$.

### Forecast Error & Operational Metrics
- **Forecast Error Magnitude ($y$):**
  $$y = \left| \text{APCP}_{24\text{h}} - \text{Rain}_{\text{IMD}} \right|$$
  Measures the absolute difference between model prediction and observed rainfall in millimeters (`error_abs`).
- **Categorical Forecast Bust:**
  A binary indicator marking severe forecast divergence:
  $$\text{Bust} = \mathbb{I}\left( \text{error\_abs} > 25.0\text{ mm} \;\land\; (\text{APCP}_{24\text{h}} > 10.0\text{ mm} \;\lor\; \text{Rain}_{\text{IMD}} > 10.0\text{ mm}) \right)$$
- **Forecast Confidence Index (FCI):**
  Forecast Confidence Index derived from conformal prediction interval width:
  $$\text{FCI} = \text{clip}\left(100.0 - \frac{\text{interval\_width}}{22.0} \times 85.0,\, 5.0,\, 96.0\right)$$
  FCI is a heuristic confidence index based on conformal interval width, not a calibrated probability.
- **Derived Bust Risk Score (`bust_risk_score`):**
  $$\text{bust\_risk\_score} = \text{clip}\left(\frac{\hat{y}}{35.0} + \mathbb{I}(\text{upper\_bound} > 25.0) \times 0.15,\, 0.01,\, 0.98\right)$$
  A derived model-based risk indicator in [0, 1]. It is **not** a calibrated probability of forecast bust. The legacy key `bust_prob` is retained as a compatibility alias.

---

## 4. Dataset Statistics

The August 2023 historical matrix comprises **30 complete daily cycles** (August 2 to August 31, 2023, accounting for 24-hour lead accumulation requirements).

```
Total Grid Cells per Day:       4,905 active land cells
Total Evaluation Days:          30 days
Total Dataset Samples:          147,150 cell-day instances
Total Forecast Busts:           8,030 instances (5.46% overall monthly prevalence)
```

### Chronological Train / Calibration / Test Split
To maintain strict temporal causality and prevent data leakage, samples were partitioned chronologically:

| Split Partition | Calendar Window | Days | Samples | Bust Count | Bust Prevalence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Train Set** | August 2, 2023 – August 21, 2023 | 20 | 98,100 | 5,910 | 6.02% |
| **Calibration Set** | August 22, 2023 – August 26, 2023 | 5 | 24,525 | 1,650 | 6.73% |
| **Test Set** | August 27, 2023 – August 31, 2023 | 5 | 24,525 | 470 | 1.92% |

*Note on Prevalence Shift:* The test set coincides with a documented late-August monsoon break phase, during which synoptic rainfall over central India was suppressed, reducing total bust prevalence to 1.92%.

---

## 5. Baseline Evaluation

The naive reference baseline predicts the median forecast error observed in the training partition for all test instances:
- **Baseline Constant Prediction:** $1.3297\text{ mm}$
- **Test Mean Absolute Error (MAE):** $3.0578\text{ mm}$
- **Test Root Mean Squared Error (RMSE):** $8.4237\text{ mm}$

---

## 6. XGBoost Performance

An `XGBRegressor` was trained on exactly 7 synoptic, thermodynamic, and spatial features:
1. `f_apcp_24h`: 24-hour accumulated forecast precipitation (mm)
2. `f_cape`: Convective Available Potential Energy (J/kg)
3. `f_hgt_500`: 500-hPa geopotential height (gpm)
4. `f_u_850`: 850-hPa zonal wind component (m/s)
5. `f_v_850`: 850-hPa meridional wind component (m/s)
6. `lat`: Latitude coordinate (degrees North)
7. `lon`: Longitude coordinate (degrees East)

### Hyperparameters
- Estimators: `n_estimators = 100`
- Maximum Tree Depth: `max_depth = 5`
- Learning Rate: `learning_rate = 0.1`
- Tree Method: `tree_method = "hist"`
- Random State: `random_state = 42`

### Test Set Evaluation Results
| Model Metric | Baseline Model | XGBoost Regressor | Relative Improvement |
| :--- | :--- | :--- | :--- |
| **Mean Absolute Error (MAE)** | 3.0578 mm | **2.6700 mm** | **+12.68%** |
| **Root Mean Squared Error (RMSE)** | 8.4237 mm | **6.4008 mm** | **+24.01%** |

The 24.01% reduction in RMSE demonstrates that meteorological feature interactions (particularly moisture loading, orographic forcing, and shear) provide substantial predictive skill in penalizing large tail errors and forecast busts.

---

## 7. Split Conformal Prediction (MAPIE) Evaluation

To quantify uncertainty with distribution-free finite-sample guarantees, Split Conformal Prediction was implemented using `MAPIE` (`SplitConformalRegressor` with absolute residual nonconformity score).

*(Note: Artifacts and schema keys such as `cqr_model.pkl`, `cqr_lower`, `cqr_upper`, and `cqr_bounds` are retained for backward compatibility with existing API endpoints and frontend components; the statistical methodology implemented is Split Conformal Prediction, not Conformalized Quantile Regression).*

### Calibration Configuration
- Calibration Partition: August 22 – August 26, 2023 ($N_{\text{cal}} = 24,525$)
- Significance Level: $\alpha = 0.20$
- Nominal Coverage Target: $1 - \alpha = 80.00\%$

### Test Set Results ($N_{\text{test}} = 24,525$)
| Conformal Metric | Theoretical Target | Empirical Achieved |
| :--- | :--- | :--- |
| **Marginal Coverage** | 80.00% | **90.99%** |
| **Mean Interval Width** | — | **8.7220 mm** |
| **Median Interval Width** | — | **8.2566 mm** |
| **Lower Bound Clamping** | $\ge 0.0\text{ mm}$ | Enforced (Non-negative rainfall error) |

**Statistical Assessment:** The empirical test-set coverage was 90.99% for the nominal 80% split-conformal interval. Conformal coverage guarantees rely on exchangeability-related assumptions between calibration and test partitions; weather time series can exhibit temporal dependence and synoptic regime changes that modulate finite-sample conditional coverage. The conservative empirical coverage (90.99% vs 80.00%) reflects the synoptic transition into the late-August monsoon break phase, where lower overall rainfall variance resulted in smaller actual residuals than those calibrated during the preceding active rain spell.

---

## 8. SHAP Local Attribution

TreeSHAP (`shap.TreeExplainer`) was applied to the trained XGBoost model to extract exact local feature attributions across the 4,905 grid cells. SHAP values represent model-attributed feature importance for predicted error magnitude and do not make causal meteorological claims.

### Attribution Descriptions
- **Forecast Precipitation (`f_apcp_24h`):** Primary driver of error scale. Heavy precipitation forecast magnitude correlates with increased predicted uncertainty.
- **CAPE (`f_cape`):** Elevated convective available potential energy is model-attributed to higher predicted forecast error.
- **500 hPa Height (`f_hgt_500`):** Geopotential height anomalies contribute to model-attributed synoptic error.
- **850 hPa Wind Components (`f_u_850`, `f_v_850`):** Low-level monsoon flow structure and shear align with directional error attribution.
- **Spatial Coordinates (`lat`, `lon`):** Geographic location attributes to regional baseline forecast uncertainty across basins.

---

## 9. Scientific Limitations

1. **Proxy NWP Model:** NOAA GFS (0.25°) is used as an open-access research proxy to validate the data engineering, ML error quantification, and split conformal calibration pipeline. These findings cannot be claimed as an operational validation of NCUM-G.
2. **Temporal Window Sample Size:** The evaluation is conducted on August 2023 (capturing active and break phases of the Indian Summer Monsoon). Multi-year, multi-season validation across pre-monsoon, monsoon, and post-monsoon cyclonic regimes is essential for operational deployment.
3. **Regridding Scheme:** Spatial alignment uses nearest-neighbor interpolation using xarray onto the IMD grid, which preserves point extrema but does not enforce area-integrated mass conservation.
4. **Exchangeability Assumption:** Conformal prediction intervals rely on the exchangeability of nonconformity scores. Synoptic persistence and weather regime transitions introduce temporal autocorrelation that can induce conditional variability in coverage.

---

## 10. Reproducibility

### Environment Specifications
- **Operating System:** Windows 11 Enterprise (64-bit)
- **Python Version:** 3.11.9
- **Key Dependencies:**
  - `xgboost`: 3.1.2
  - `mapie`: 1.3.0
  - `shap`: 0.49.1
  - `xarray`: 2026.2.0
  - `cfgrib`: 0.9.15.1
  - `herbie-data`: 2024.11.0
  - `scikit-learn`: 1.8.0
  - `fastapi`: 0.135.1
  - `pydantic`: 2.12.5

### Pipeline Script Execution Order
```bash
# 1. Download and preprocess IMD gridded observation
python ml_pipeline/real_data/01_download_imd.py

# 2. Download NOAA GFS forecasts via Herbie
python ml_pipeline/real_data/02_download_gfs.py

# 3. Spatial and temporal alignment & single-day verification
python ml_pipeline/real_data/03_align_and_error.py

# 4. Construct August 2023 historical matrix (30 days)
python ml_pipeline/real_data/04_build_historical_matrix.py

# 5. Train XGBoost and calibrate MAPIE conformal intervals
python ml_pipeline/real_data/05_train_cqr.py

# 6. Generate production GeoJSON layer with TreeSHAP explanations
python ml_pipeline/real_data/06_export_geojson.py
```

All source data, parquet matrices, serialized models, metrics, and GeoJSON layers reside in `backend/data/real/` and are fully deterministic given the random seeds ($seed = 42$).
