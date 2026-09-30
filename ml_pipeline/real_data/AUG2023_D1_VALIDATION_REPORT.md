# VISHWAS: August 2023 D+1 Real-Data Validation Report

> **Executive Scientific Summary:**
> This report documents the strengthened real-data validation of VISHWAS on the August 2023 evaluation dataset (D+1 forecast horizon, 24-hour rainfall accumulation). Evaluating against 24,525 independent test-set instances (August 27–31, 2023), the gradient-boosted error regressor achieves a **12.68% reduction in MAE** (2.6700 mm vs. 3.0578 mm baseline) and a **24.01% reduction in RMSE** (6.4008 mm vs. 8.4237 mm baseline). Marginal empirical coverage for the 80% Split Conformal Prediction interval achieves **90.99%** under chronological partitioning, with a median interval width of **8.2566 mm**. Applying the established forecast-bust criterion to predicted errors yields a **Precision of 58.33%** and **Specificity of 99.56%** at an overall accuracy of **98.25%**.

---

## 1. Objective

The primary objective of this validation is to rigorously quantify the performance of the VISHWAS numerical weather prediction (NWP) reliability engine against historical meteorological observations over the Indian subcontinent. Specifically, this evaluation:
1. Benchmarks gradient-boosted forecast error predictions against a naive median baseline.
2. Evaluates the capacity of continuous error predictions to detect extreme localized forecast busts using the established threshold criteria.
3. Stratifies forecast error across observed rainfall intensity regimes to identify non-linear scaling behaviors.
4. Assesses finite-sample conformal prediction interval coverage and width under chronological evaluation.
5. Formulates explicit, scientifically defensible distinctions between measured observational errors, derived risk heuristics, theoretical assumptions, and operational constraints.

---

## 2. Dataset & Provenance

The validation utilizes freely accessible historical datasets spanning August 1 to August 31, 2023 across mainland India:

| Parameter | Numerical Weather Prediction (NWP) | Observational Reference |
| :--- | :--- | :--- |
| **Data Source** | NOAA Global Forecast System (GFS) 0.25° Open Data | India Meteorological Department (IMD) Pune Archive |
| **Access Pipeline** | `herbie-data` (2024.11.0) automated retrieval from AWS S3 | IMD gridded daily rainfall NetCDF4 archive (`imdlib`) |
| **Grid Resolution** | 0.25° × 0.25° regular latitude/longitude (~27 km) | 0.25° × 0.25° regular latitude/longitude |
| **Spatial Domain** | Lat 8.0°–36.0°N, Lon 68.0°–98.0°E (Indian landmass) | Lat 8.0°–36.0°N, Lon 68.0°–98.0°E (4,905 active land cells) |
| **Initialization Cycle** | 00:00 UTC daily | Daily accumulation recorded at 08:30 IST (03:00 UTC) |
| **Forecast Horizons** | +3h (F03) and +27h (F27) forecast lead times | 24-hour gauge-interpolated accumulation (Day 0 03:00 UTC to Day +1 03:00 UTC) |
| **Evaluation Scope** | August 2, 2023 to August 31, 2023 (30 valid cycles) | August 2, 2023 to August 31, 2023 (30 valid cycles) |
| **Total Samples** | 147,150 cell-day instances ($30 \times 4,905$) | 147,150 cell-day instances ($30 \times 4,905$) |

> **Important Operational Distinction:** NOAA GFS 0.25° is employed strictly as an open-access NWP research proxy to validate pipeline mechanics, error regressor architectures, and conformal inference. It is **NOT** an operational validation of NCMRWF's NCUM-G model.

---

## 3. Forecast/Observation Alignment

### Spatial Regridding
The spatial reference coordinate system is defined by the 4,905 active terrestrial grid cells of the IMD 0.25° network. Oceanic cells and non-reporting trans-boundary cells are omitted. GFS longitudes ($0^\circ \text{ to } 360^\circ$) are converted to Greenwich standard ($68^\circ \text{ to } 98^\circ\text{E}$). Spatial regridding of GFS fields onto IMD points is conducted via **nearest-neighbor interpolation using xarray** (`xarray.Dataset.interp(method="nearest")`), avoiding smoothing or distortion of extreme localized convective values.

### Temporal Accumulation Alignment
GFS total precipitation (`APCP`) is reported as cumulative rainfall from model reset:
- Forecast Step +3h (`APCP`): Accumulation from 00:00 UTC to 03:00 UTC on Day 0.
- Forecast Step +27h (`APCP`): Accumulation from 00:00 UTC Day 0 to 03:00 UTC Day +1 (27 hours).

The valid 24-hour accumulation corresponding to the IMD 08:30 IST window is computed as:
$$\text{APCP}_{24\text{h}} = \max\left(\text{APCP}_{+27\text{h}} - \text{APCP}_{+3\text{h}},\, 0.0\right)$$
Sub-zero values arising from floating-point precision artifacts are clamped strictly to $0.0\text{ mm}$.

---

## 4. Forecast Bust Definition

A binary categorical forecast bust ($Y_{\text{bust}} \in \{0, 1\}$) represents a severe, operationally disruptive divergence between forecast rainfall ($F = \text{APCP}_{24\text{h}}$) and observational reference ($O = \text{Rain}_{\text{IMD}}$):

$$Y_{\text{bust}} = \mathbb{I}\left( \left| F - O \right| > 25.0\text{ mm} \;\land\; \left(F > 10.0\text{ mm} \;\lor\; O > 10.0\text{ mm}\right) \right)$$

### Scientific Rationale
1. **Severe Divergence Criterion ($\left| F - O \right| > 25.0\text{ mm}$):** Focuses verification on large absolute discrepancies capable of impacting flood warnings, reservoir scheduling, or disaster preparedness.
2. **Precipitation Activity Guard ($F > 10.0\text{ mm} \;\lor\; O > 10.0\text{ mm}$):** Eliminates false-positive alerts in dry synoptic conditions where small discrepancies would otherwise trigger alerts without hydrological significance.

---

## 5. Temporal Partitioning

To maintain strict physical causality and avoid temporal data leakage, samples are partitioned strictly by calendar date:

| Partition | Date Window | Days | Samples | Bust Count | Bust Prevalence | Role in Pipeline |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Training Set** | Aug 2 – Aug 21, 2023 | 20 | 98,100 | 5,570 | 5.68% | Fit XGBoost regressor |
| **Calibration Set** | Aug 22 – Aug 26, 2023 | 5 | 24,525 | 1,990 | 8.11% | Calibrate MAPIE Split Conformal intervals |
| **Test Set** | Aug 27 – Aug 31, 2023 | 5 | 24,525 | 470 | 1.92% | Independent out-of-sample evaluation |

```
Temporal Order Assertion: max(Train: Aug 21) < min(Calib: Aug 22) < min(Test: Aug 27) [STRICTLY SATISFIED]
```

*Synoptic Shift Note:* The drop in test-set bust prevalence (1.92% vs 8.11% in calibration) reflects a documented late-August monsoon break phase, during which large-scale convective rainfall across central India subsided.

---

## 6. Model Specification

### Architecture
- **Model Type:** Extreme Gradient Boosting Regressor (`xgboost.XGBRegressor`)
- **Target Variable:** Continuous absolute forecast error: $y = \left| F - O \right|$ (`error_abs`)
- **Loss Function:** Squared error (`reg:squarederror`)
- **Tree Method:** Fast histogram-based partitioning (`tree_method="hist"`)

### Hyperparameters
- Number of Trees (`n_estimators`): 100
- Maximum Tree Depth (`max_depth`): 5
- Learning Rate (`learning_rate`): 0.1
- Random Seed (`random_state`): 42

### Input Feature Set (7 Predictors)
1. `f_apcp_24h`: Forecast 24h precipitation accumulation (mm)
2. `f_cape`: Convective Available Potential Energy (J/kg)
3. `f_hgt_500`: 500-hPa geopotential height (gpm)
4. `f_u_850`: 850-hPa zonal wind velocity (m/s)
5. `f_v_850`: 850-hPa meridional wind velocity (m/s)
6. `lat`: Latitude coordinate (°N)
7. `lon`: Longitude coordinate (°E)

---

## 7. Regression Results

Performance on the independent test set ($N_{\text{test}} = 24,525$) is benchmarked against a naive reference model predicting the constant training target median ($1.3297\text{ mm}$):

| Evaluation Metric | Baseline Model | XGBoost Regressor | Relative Improvement |
| :--- | :--- | :--- | :--- |
| **Mean Absolute Error (MAE)** | 3.0578 mm | **2.6700 mm** | **+12.68%** |
| **Root Mean Squared Error (RMSE)** | 8.4237 mm | **6.4008 mm** | **+24.01%** |
| **Mean Bias ($\hat{y} - y$)** | +0.6728 mm | **+1.0402 mm** | Conservative error over-estimation |
| **Median Absolute Error** | 0.9022 mm | **1.2004 mm** | — |
| **Maximum Absolute Error** | 224.2881 mm | **224.2881 mm** | Unresolved extreme localized convective burst |

### Subgroup Regression Analysis
- **Non-Bust Instances ($N = 24,055$, 98.08% of test set):**
  - MAE: **2.1737 mm**
  - RMSE: **3.9546 mm**
  - Mean Bias: **+1.4799 mm**
  - Median Absolute Error: **1.1608 mm**
- **Bust Instances ($N = 470$, 1.92% of test set):**
  - MAE: **28.0739 mm**
  - RMSE: **36.5709 mm**
  - Mean Bias: **-21.4622 mm** (Under-prediction of extreme localized burst peaks)
  - Median Absolute Error: **22.8532 mm**

*Interpretation:* The regressor achieves substantial error reduction across the dominant non-bust regime. In extreme bust scenarios (tail error > 25 mm), the model predicts elevated error ($\bar{\hat{y}} = 8.52\text{ mm}$ vs $3.97\text{ mm}$ for non-bust), but structurally underestimates the most extreme peaks, reflecting the known regression-to-the-mean property of gradient-boosted trees under standard $L_2$ loss.

---

## 8. Bust Classification Diagnostics

While the primary model predicts continuous error magnitude, operational meteorologists require categorical thresholds for warnings. Two defensible decision rules established in the repository were evaluated against ground-truth busts:

### Rule A: Predicted-Error Operational Alert Rule
$$\widehat{Y}_{\text{bust}} = \mathbb{I}\left( \hat{y} > 25.0\text{ mm} \;\land\; F > 10.0\text{ mm} \right)$$
Evaluates whether a model predicting continuous error $\hat{y} > 25.0\text{ mm}$ in a forecast-rainy zone ($F > 10.0\text{ mm}$) identifies an actual bust.

> **Important Scientific Distinction:** In Rule A, "$F > 10\text{ mm}$" is the forecast-side operational approximation used for the predicted-error alert rule (available at forecast inference time before observations arrive). It is **NOT** identical to the ground-truth bust definition, which remains strictly:
> $$\left| F - O \right| > 25.0\text{ mm} \;\land\; \left(F > 10.0\text{ mm} \;\lor\; O > 10.0\text{ mm}\right)$$
- **True Positives (TP):** 147
- **False Positives (FP):** 105
- **True Negatives (TN):** 23,950
- **False Negatives (FN):** 323
- **Precision (PPV):** **58.33%** (147 / 252)
- **Recall (Sensitivity):** **31.28%** (147 / 470)
- **F1 Score:** **0.4072**
- **Accuracy:** **98.25%** (24,097 / 24,525)
- **Specificity (TNR):** **99.56%** (23,950 / 24,055)
- **Balanced Accuracy:** **65.42%**
- **Matthews Correlation Coefficient (MCC):** **0.4193**

### Rule B: Established Operational Alert Threshold (`bust_risk_score >= 0.70`)
Uses the backend operational alert threshold derived from normalized error and conformal upper bounds:
$$\text{bust\_risk\_score} = \text{clip}\left(\frac{\hat{y}}{35.0} + \mathbb{I}(\text{upper} > 25.0) \times 0.15,\, 0.01,\, 0.98\right) \ge 0.70$$
- **True Positives (TP):** 175
- **False Positives (FP):** 266
- **True Negatives (TN):** 23,789
- **False Negatives (FN):** 295
- **Precision (PPV):** **39.68%** (175 / 441)
- **Recall (Sensitivity):** **37.23%** (175 / 470)
- **F1 Score:** **0.3842**
- **Accuracy:** **97.71%** (23,964 / 24,525)
- **Specificity (TNR):** **98.89%** (23,789 / 24,055)
- **Balanced Accuracy:** **68.06%**
- **Matthews Correlation Coefficient (MCC):** **0.3727**

### Diagnostic Rule C: Conformal Prediction Upper Bound Exceeding 25 mm (`cqr_upper > 25.0 mm`)
- **TP:** 179 | **FP:** 275 | **TN:** 23,780 | **FN:** 291
- **Precision:** **39.43%** | **Recall:** **38.09%** | **Balanced Accuracy:** **68.47%** | **MCC:** **0.3757**

> **Scientific Clarification:** The model is trained on continuous error $|F - O|$, not as a binary classifier. The `bust_risk_score` is a derived operational risk index in [0, 1] and must **not** be interpreted as a calibrated posterior probability of bust occurrence.

---

## 9. Rainfall-Intensity Stratification

To evaluate error scaling across precipitation intensity regimes, test cases were stratified by observed IMD rainfall ($O = \text{Rain}_{\text{IMD}}$):

| Observed Rain Bin | Sample Count | Pct of Test Set | MAE (mm) | RMSE (mm) | Mean Bias (mm) | Characterization |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **0–10 mm** | 22,734 | 92.70% | 1.7698 | 2.7556 | +1.4264 | Light / Nil Rain (Dominant regime) |
| **10–25 mm** | 999 | 4.07% | 7.2560 | 8.5222 | +0.1967 | Moderate Rainfall |
| **25–50 mm** | 575 | 2.34% | 14.7624 | 17.2235 | -5.6821 | Rather Heavy Rain |
| **50–100 mm** | 174 | 0.71% | 36.2978 | 39.8036 | -9.5398 | Heavy Rainfall |
| **>100 mm** | 43 | 0.18% | 74.2989 | 85.3665 | -50.8454 | Very Heavy / Extreme Convective Events |
| **Total Verified** | **24,525** | **100.00%** | **2.6700** | **6.4008** | **+1.0402** | Exact test-set coverage |

### Key Findings
1. **Low-Rain Regime Mastery:** In the 0–10 mm regime (92.7% of the test set), model MAE is just 1.77 mm, with a slight conservative positive bias (+1.43 mm).
2. **Monotonic Error Growth:** Both MAE and RMSE scale monotonically with precipitation intensity, reflecting heteroskedastic atmospheric variance.
3. **Extreme Event Underestimation:** Above 50 mm, the model exhibits negative bias (-9.54 mm and -50.85 mm for >100 mm), illustrating the difficulty of predicting the absolute peak magnitude of localized mesoscale cloudbursts with 0.25° gridded synoptic predictors.

---

## 10. Split Conformal Prediction Analysis

Uncertainty quantification was implemented via `MAPIE` (`SplitConformalRegressor`) with a nominal 80% coverage target ($\alpha = 0.20$):

| Conformal Metric | Theoretical Target | Empirical Achieved |
| :--- | :--- | :--- |
| **Marginal Coverage** | 80.00% | **90.99%** |
| **Mean Interval Width** | — | **8.7220 mm** |
| **Median Interval Width** | — | **8.2566 mm** |
| **Lower Bound Clamping** | $\ge 0.0\text{ mm}$ | Enforced |

### Diagnostic Subgroup Coverage (Informational Only)
- **Non-Bust Instances ($N = 24,055$):**
  - Empirical Coverage: **92.60%**
  - Mean Width: **8.6658 mm** | Median Width: **8.1815 mm**
- **Bust Instances ($N = 470$):**
  - Empirical Coverage: **8.30%**
  - Mean Width: **11.5997 mm** | Median Width: **11.8610 mm**

### Statistical Context
- **Marginal vs. Conditional Validity:** The marginal Split Conformal Prediction guarantee holds unconditionally across the exchangeable sample space. It does **not** guarantee coverage conditionally within extreme-tail subgroups selected post-hoc by high error values ($> 25\text{ mm}$).
- **Conservative Marginal Coverage (90.99% vs 80.00%):** The higher-than-nominal empirical coverage is attributed to the late-August synoptic transition into a monsoon break phase, during which observational variance was lower than in the active monsoon calibration phase (August 22–26).

---

## 11. Error and Rainfall Distribution Quantiles

Distributional summaries across the 24,525 test instances provide a detailed view of error and rainfall dispersion:

### Quantile Summary Table (values in mm)

| Variable | P10 | P25 | P50 (Median) | P75 | P90 | P95 | P99 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Model Absolute Error ($|\hat{y} - y|$)** | 0.1318 | 0.3783 | 1.2004 | 2.9654 | 5.5662 | 8.7343 | 24.6977 |
| **Model Signed Residual ($\hat{y} - y$)** | -0.3579 | +0.1445 | +0.8802 | +2.3708 | +4.5631 | +6.2332 | +13.4711 |
| **NWP Absolute Error ($|F - O|$)** | 0.0000 | 0.0000 | 0.4772 | 2.7500 | 7.5433 | 12.7909 | 36.8658 |
| **NWP Signed Error ($F - O$)** | -1.3330 | 0.0000 | +0.1250 | +1.4540 | +4.6875 | +7.8125 | +19.6250 |
| **Forecast Precipitation ($F$)** | 0.0000 | 0.0000 | 0.4375 | 2.7500 | 7.8750 | 13.6875 | 37.6275 |
| **Observed Rainfall ($O$)** | 0.0000 | 0.0000 | 0.0000 | 0.3078 | 6.3139 | 16.2219 | 46.7577 |

### Distributional Observations
- At the median (P50), NWP forecast error is modest ($0.48\text{ mm}$), and model residual is $1.20\text{ mm}$.
- At the 95th percentile, NWP error expands to $12.79\text{ mm}$, and at the 99th percentile, it reaches $36.87\text{ mm}$.
- Forecast precipitation exhibits a maximum 99th percentile of $37.63\text{ mm}$, whereas observational gauge extremes reach $46.76\text{ mm}$ at P99 and up to $225\text{ mm}$ peak point values.

---

## 12. Scientific Limitations & Boundaries

1. **Research Proxy Status:** NOAA GFS 0.25° is an open-access global research proxy. These results validate data pipelines and ML architectures, but cannot be claimed as an operational validation of NCUM-G or NEPS-G.
2. **Temporal Window:** The dataset spans August 2023 only. Multi-season validation spanning winter, pre-monsoon convective outbreaks, and post-monsoon tropical cyclones is necessary before operational deployment.
3. **Lead Time Horizon:** This evaluation is conducted at D+1 (+24h accumulation). Medium-range horizons (D+3 to D+10) exhibit different error growth dynamics that require dedicated multi-horizon calibration.
4. **Exchangeability Assumptions:** Conformal prediction intervals rely on the exchangeability of nonconformity scores. Synoptic persistence, monsoon active-break cycles, and regional topography introduce spatio-temporal dependencies that can induce finite-sample coverage variation.
5. **Heuristic Risk Score:** The `bust_risk_score` is a derived operational index combining normalized error and conformal bounds. It is **not** a calibrated posterior probability of forecast bust.
6. **Local Attribution vs. Causality:** TreeSHAP feature attributions describe how the XGBoost regressor weights input features to arrive at its prediction; they do not represent causal physical proofs of atmospheric mechanisms.

---

## 13. Reproducibility Information

### Execution Commands
```bash
# 1. Execute the comprehensive validation evaluation
python ml_pipeline/real_data/07_evaluate_validation.py

# 2. Run unit tests verifying alignment and mathematical constraints
python -m pytest ml_pipeline/tests/test_real_data_alignment.py -v

# 3. Verify backend integration with real data mode
python -m pytest backend/test_api.py -v
```

### Generated Artifacts
- **Structured Metrics JSON:** `ml_pipeline/real_data/aug2023_d1_validation_metrics.json`
- **Validation Report:** `ml_pipeline/real_data/AUG2023_D1_VALIDATION_REPORT.md`
- **Model Checkpoint:** `backend/data/real/models/cqr_model.pkl`
- **Training Metrics Baseline:** `backend/data/real/models/cqr_metrics.json`
