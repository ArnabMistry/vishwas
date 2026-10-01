# VISHWAS Phase 1B: Multi-Month Real-Data Validation Report
**Evaluation Months:** July 2023, August 2023 (Baseline), September 2023  
**Forecast Cycle:** 00:00 UTC Initialization | Lead Time: D+1 (+3h to +27h accumulation difference)  
**NWP Source:** NOAA Global Forecast System (GFS) 0.25° Open Data Research Proxy  
**Observational Reference:** India Meteorological Department (IMD) 0.25° Daily Gridded Rainfall  
**Spatial Domain:** Lat 8.0°–36.0°N, Lon 68.0°–98.0°E (4,905 active terrestrial cells)  
**Total Volume Evaluated:** 441,450 cell-days (90 valid dates across 3 calendar months)

---

## 1. Executive Summary

This report documents the multi-month real-data evaluation of VISHWAS across three distinct months of the 2023 Indian Summer Monsoon: **July 2023** (peak active monsoon regime), **August 2023** (extended monsoon break regime; Phase 1A baseline), and **September 2023** (revival and subsequent withdrawal regime).

The primary objective is to evaluate whether the gradient-boosted error regressor and Split Conformal Prediction engine exhibit consistent behavioral characteristics across heterogeneous synoptic conditions, assess performance under pooled retrospective multi-month training, and quantify statistical transfer under leave-one-month-out cross-month evaluation.

### Key Measured Highlights
1. **Regression Improvements Across All Evaluated Months:**
   - In **July 2023**, the model achieves a **25.05% reduction in MAE** (6.2544 mm vs. 8.3446 mm baseline) and **34.11% reduction in RMSE** (12.3600 mm vs. 18.7591 mm).
   - In **August 2023** (authoritative Phase 1A), the model achieves a **12.68% reduction in MAE** (2.6700 mm vs. 3.0578 mm) and **24.01% reduction in RMSE** (6.4008 mm vs. 8.4237 mm).
   - In **September 2023**, the model achieves a **36.80% reduction in MAE** (2.7478 mm vs. 4.3476 mm) and **30.42% reduction in RMSE** (5.6328 mm vs. 8.0954 mm).
2. **Conformal Coverage Adherence:**
   Marginal empirical coverage for the 80% nominal Split Conformal Prediction interval achieves **84.25% in July**, **90.99% in August**, and **91.04% in September**, meeting the nominal 80% target under the exchangeability assumption across all three independent monthly replications. Under pooled 3-month retrospective evaluation, marginal coverage stands at **88.44%**.
3. **Bust Alert Mechanics:**
   In July (test-set bust prevalence 9.10%), Rule A achieves **F1 = 0.5254** (Precision 74.45%, Recall 40.59%) and Rule B achieves **F1 = 0.5614** (Precision 57.21%, Recall 55.11%). In August (test-set bust prevalence 1.92%), Rule A achieves **F1 = 0.4072** and Rule B achieves **F1 = 0.3842**. In September (test-set bust prevalence 2.48%), Rule A achieves **F1 = 0.2725** (Precision 92.38%, Recall 15.98%) and Rule B achieves **F1 = 0.3663**.
4. **Rainfall-Intensity Scaling:**
   Across all three months, forecast error scales with observed rainfall intensity: for observed rain between 0–10 mm, XGBoost MAE is 1.77–3.63 mm; for convective rain >100 mm, MAE reaches 66.85–74.30 mm.

---

## 2. Dataset Description and Population Scopes

The evaluation uses strictly aligned daily gridded forecasts and observations over the Indian landmass. Spatial alignment is conducted via nearest-neighbor interpolation on the IMD grid, retaining exactly 4,905 active land cells per day.

> **Important Population Scope Distinction:**
> The analysis operates on two distinct populations that are explicitly separated in this report:
> 1. **Full-Month Dataset Population (30 valid days, 147,150 cell-days per month):** Captures total monthly climatology, full-month bust counts, and regional rainfall distributions.
> 2. **Evaluation Test-Set Partition (final 5 valid days, 24,525 cell-days per month):** The strictly held-out out-of-sample partition used to benchmark regression accuracy, conformal coverage, and bust alert rules.

### TABLE 1A — FULL-MONTH DATASET POPULATION SUMMARY (147,150 ROWS PER MONTH)
| Month | Total Valid Days | Total Rows | Full-Month Bust Count | Full-Month Bust Prevalence |
| :--- | :---: | :---: | :---: | :---: |
| **July 2023** | 30 | 147,150 | 15,137 | **10.29%** |
| **August 2023** (Baseline) | 30 | 147,150 | 8,030 | **5.46%** |
| **September 2023** | 30 | 147,150 | 7,599 | **5.16%** |
| **Total / Pooled Full Months** | **90** | **441,450** | **30,766** | **6.97%** |

### TABLE 1B — EVALUATION TEST-SET PARTITION SUMMARY (FINAL 5 VALID DAYS, 24,525 ROWS PER MONTH)
| Month | Test Date Window | Test N | Test Bust Count | Test Bust Prevalence |
| :--- | :---: | :---: | :---: | :---: |
| **July 2023** | 2023-07-27 to 2023-07-31 | 24,525 | 2,232 | **9.10%** |
| **August 2023** (Baseline) | 2023-08-27 to 2023-08-31 | 24,525 | 470 | **1.92%** |
| **September 2023** | 2023-09-26 to 2023-09-30 | 24,525 | 607 | **2.48%** |
| **Combined Pooled Test Set** | (15 days combined) | 73,575 | 3,309 | **4.50%** |

*Ground-Truth Bust Definition:*  
$$\text{Bust} = \mathbb{I}\left( \left| F - O \right| > 25.0\text{ mm} \;\land\; \left(F > 10.0\text{ mm} \;\lor\; O > 10.0\text{ mm}\right) \right)$$

---

## 3. Exact Month and Date Splits

To preserve temporal causality and avoid data leakage across convective cycles, every monthly dataset is partitioned chronologically into 20 training days, 5 calibration days, and 5 out-of-sample test days:

| Month | Partition | Valid Date Range | Days | Cell-Day Instances | Busts | Bust Prevalence |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **July 2023** | Train | 2023-07-02 to 2023-07-21 | 20 | 98,100 | 10,670 | 10.88% |
| | Calibration | 2023-07-22 to 2023-07-26 | 5 | 24,525 | 2,235 | 9.11% |
| | Test | 2023-07-27 to 2023-07-31 | 5 | 24,525 | 2,232 | 9.10% |
| **August 2023** | Train | 2023-08-02 to 2023-08-21 | 20 | 98,100 | 5,570 | 5.68% |
| | Calibration | 2023-08-22 to 2023-08-26 | 5 | 24,525 | 1,990 | 8.11% |
| | Test | 2023-08-27 to 2023-08-31 | 5 | 24,525 | 470 | 1.92% |
| **September 2023** | Train | 2023-09-01 to 2023-09-20 | 20 | 98,100 | 5,283 | 5.39% |
| | Calibration | 2023-09-21 to 2023-09-25 | 5 | 24,525 | 1,719 | 7.01% |
| | Test | 2023-09-26 to 2023-09-30 | 5 | 24,525 | 607 | 2.48% |

*Temporal Ordering Assertion:* $\max(\text{Train}) < \min(\text{Calib}) < \min(\text{Test})$ is strictly satisfied for all partitions.

---

## 4. Experiment A: Month-by-Month Replication

In Experiment A, an independent XGBoost regressor (100 estimators, max depth 5, learning rate 0.1, tree method `hist`) and MAPIE Split Conformal Regressor (nominal coverage 80%) are trained and calibrated separately within each calendar month. August 2023 preserves the exact authoritative Phase 1A baseline results.

### TABLE 2 — MONTHLY REGRESSION METRICS (TEST SET, N = 24,525 PER MONTH)
| Month | Baseline MAE | XGBoost MAE | Baseline RMSE | XGBoost RMSE | MAE Imp. (%) | RMSE Imp. (%) | Mean Bias | Median AE | Max AE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **July 2023** | 8.3446 mm | 6.2544 mm | 18.7591 mm | 12.3600 mm | **+25.05%** | **+34.11%** | +0.4691 mm | 2.9463 mm | 385.55 mm |
| **August 2023** | 3.0578 mm | 2.6700 mm | 8.4237 mm | 6.4008 mm | **+12.68%** | **+24.01%** | +1.0402 mm | 1.2004 mm | 224.29 mm |
| **September 2023** | 4.3476 mm | 2.7478 mm | 8.0954 mm | 5.6328 mm | **+36.80%** | **+30.42%** | +0.1886 mm | 1.3411 mm | 185.34 mm |

*Observation on Regression Behavior:*
- Across all three months, XGBoost reduces both MAE and RMSE relative to the training-median baseline.
- Absolute error magnitudes correlate with prevailing monsoon activity: July exhibits substantially higher baseline and model MAE (6.25 mm) than August (2.67 mm) and September (2.75 mm), reflecting the higher rainfall volume observed during active monsoon conditions.

---

## 5. Conformal Interval Metrics

Conformal prediction intervals are produced via MAPIE `SplitConformalRegressor` with `confidence_level=0.80`.

### TABLE 3 — CONFORMAL PREDICTION METRICS (TEST SET, N = 24,525 PER MONTH)
| Month | Nominal Coverage | Empirical Marginal Coverage | Mean Interval Width | Median Interval Width | Min Interval Width | Max Interval Width |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **July 2023** | 80.0% | **84.25%** | 16.3487 mm | 17.7167 mm | 8.8584 mm | 17.7167 mm |
| **August 2023** | 80.0% | **90.99%** | 8.7220 mm | 8.2566 mm | 4.1283 mm | 8.2566 mm |
| **September 2023** | 80.0% | **91.04%** | 10.0986 mm | 9.8171 mm | 4.9086 mm | 9.8171 mm |

### Diagnostic Subgroup Coverage Statistics
- **July 2023:**
  - Non-bust subgroup coverage: **88.66%** ($N = 22,293$, mean width: 15.86 mm)
  - Bust subgroup coverage: **40.59%** ($N = 2,232$, mean width: 21.21 mm)
- **August 2023:**
  - Non-bust subgroup coverage: **92.60%** ($N = 24,055$, mean width: 8.67 mm)
  - Bust subgroup coverage: **8.30%** ($N = 470$, mean width: 11.60 mm)
- **September 2023:**
  - Non-bust subgroup coverage: **93.00%** ($N = 23,918$, mean width: 10.04 mm)
  - Bust subgroup coverage: **13.98%** ($N = 607$, mean width: 12.38 mm)

> **Scientific Caveat on Coverage:**
> Split Conformal Prediction provides marginal coverage under the exchangeability assumption across the general sample space. Conditional or subgroup coverage on post-hoc subsets selected by extreme forecast error ($|F - O| > 25\text{ mm}$) is not guaranteed by the marginal conformal guarantee. Consequently, when large convective forecast busts occur, absolute errors frequently exceed calibrated interval bounds, while non-bust subsets achieve coverage exceeding 88%. Interval widths adjust to the calibration regime's dispersion (July mean width 16.35 mm vs. August 8.72 mm).

---

## 6. Bust-Detection Evaluation

Bust detection is evaluated under three standardized rules against the ground-truth criterion:
- **Rule A:** $\text{predicted\_error} > 25.0\text{ mm} \;\land\; \text{forecast} > 10.0\text{ mm}$ (*operational approximation; not identical to the ground-truth bust rule*).
- **Rule B:** $\text{derived\_bust\_risk\_score} \ge 0.70$ (*derived bust risk score; model-based risk indicator, not a calibrated probability*).
- **Rule C:** $\text{conformal\_upper} > 25.0\text{ mm}$ (*80% conformal upper bound alert*).

### TABLE 4 — BUST DETECTION DECISION RULES (TEST SET, N = 24,525 PER MONTH)
| Month | Rule | TP | FP | TN | FN | Precision | Recall | F1 Score | Balanced Accuracy | MCC |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **July** | **Rule A** | 906 | 311 | 21,982 | 1,326 | **0.7445** | 0.4059 | **0.5254** | 0.6960 | 0.5191 |
| | **Rule B** | 1,230 | 920 | 21,373 | 1,002 | 0.5721 | 0.5511 | **0.5614** | 0.7549 | 0.5185 |
| | **Rule C** | 1,449 | 2,329 | 19,964 | 783 | 0.3835 | **0.6492** | 0.4822 | 0.7724 | 0.4340 |
| **August** | **Rule A** | 147 | 105 | 23,950 | 323 | 0.5833 | 0.3128 | 0.4072 | 0.6542 | 0.4193 |
| | **Rule B** | 175 | 266 | 23,789 | 295 | 0.3968 | 0.3723 | 0.3842 | 0.6806 | 0.3727 |
| | **Rule C** | 179 | 275 | 23,780 | 291 | 0.3943 | 0.3809 | 0.3874 | 0.6847 | 0.3757 |
| **September** | **Rule A** | 97 | 8 | 23,910 | 510 | **0.9238** | 0.1598 | 0.2725 | 0.5797 | 0.3795 |
| | **Rule B** | 152 | 71 | 23,847 | 455 | 0.6816 | 0.2504 | 0.3663 | 0.6237 | 0.4050 |
| | **Rule C** | 168 | 100 | 23,818 | 439 | 0.6269 | 0.2768 | 0.3840 | 0.6363 | 0.4074 |

*Key Findings on Bust Rules:*
- **Rule A (Precision-Oriented):** Shows high precision across all evaluated months (74.45% in July, 58.33% in August, 92.38% in September) with conservative recall (15.98% to 40.59%).
- **Rule B (Operational Balance):** Derived risk score threshold ($\ge 0.70$) yields higher recall than Rule A (55.11% in July, 37.23% in August, 25.04% in September) while maintaining balanced accuracy between 62.37% and 75.49%.
- **Rule C (Maximum Sensitivity):** Conformal upper bound captures the highest proportion of bust cases (up to 64.92% recall in July), accompanied by a higher false positive rate in convective regimes.

---

## 7. Rainfall Intensity Stratification

Stratifying test samples by observed rainfall intensity displays consistent behavior across all three calendar months:

### TABLE 5 — RAINFALL INTENSITY REGIME ANALYSIS (EXPERIMENT A TEST SETS)
| Month | Observed Rain Bin | Sample Count ($N$) | Pct of Test Set | MAE (mm) | RMSE (mm) | Mean Bias (mm) | Bust Prevalence (%) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **July 2023** | 0–10 mm | 18,618 | 75.91% | 3.6320 | 5.0014 | +2.0757 | 3.86% |
| | 10–25 mm | 3,436 | 14.01% | 7.4144 | 8.8523 | +2.2097 | 5.82% |
| | 25–50 mm | 1,655 | 6.75% | 15.0331 | 18.7549 | -5.4928 | **36.68%** |
| | 50–100 mm | 600 | 2.45% | 33.0425 | 38.1077 | -24.4618 | **84.50%** |
| | >100 mm | 216 | 0.88% | 72.1622 | 84.9351 | -50.7643 | **92.59%** |
| **August 2023** | 0–10 mm | 22,734 | 92.70% | 1.7698 | 2.7556 | +1.4264 | 0.25% |
| | 10–25 mm | 999 | 4.07% | 7.2560 | 8.5222 | +0.1967 | 4.40% |
| | 25–50 mm | 575 | 2.34% | 14.7624 | 17.2235 | -5.6821 | **35.13%** |
| | 50–100 mm | 174 | 0.71% | 36.2978 | 39.8036 | -9.5398 | **74.71%** |
| | >100 mm | 43 | 0.18% | 74.2989 | 85.3665 | -50.8454 | **88.37%** |
| **September 2023** | 0–10 mm | 21,891 | 89.26% | 1.7926 | 2.8112 | +0.8390 | 0.85% |
| | 10–25 mm | 1,790 | 7.30% | 6.7627 | 8.0014 | -0.1363 | 1.06% |
| | 25–50 mm | 687 | 2.80% | 14.3948 | 17.3074 | -10.8251 | **36.83%** |
| | 50–100 mm | 153 | 0.62% | 38.4796 | 41.7364 | -37.8633 | **94.77%** |
| | >100 mm | 4 | 0.02% | 66.8515 | 67.5165 | -66.8515 | **100.00%** |

*Empirical Observations Across Tested Rainfall Bins:*
1. **Light Rain Regime (0–10 mm):** Dominates sample volume (75.91% in July, 92.70% in August, 89.26% in September). Forecast error is lowest in this bin (MAE 1.77–3.63 mm), with a slight positive mean bias (+0.84 to +2.08 mm).
2. **Intermediate Rainfall Regime (25–50 mm):** Measured bust prevalence in this bin is approximately: **July 36.68%, August 35.13%, and September 36.83%**.
3. **Heavy / Extreme Rainfall Regimes (>50 mm):** The evaluation shows increasing negative bias with increasing rainfall intensity in the tested bins (mean bias ranges from -9.54 to -37.86 mm in the 50–100 mm bin, and -50.76 to -66.85 mm in the >100 mm bin), accompanied by high bust prevalence (74.71% to 100.00% across the evaluated test sets).

---

## 8. Experiment B: Pooled Three-Month Retrospective Evaluation

Experiment B evaluates a unified model trained on 294,300 cell-day instances (60 training days across July, August, September) and calibrated on 73,575 instances (15 calibration days), evaluated across the combined 73,575 test instances (15 test days) as well as each monthly test subset.

> **Operational Context:** This experiment represents a pooled retrospective evaluation to observe the effect of expanded sample size under temporal separation. It is not an operational deployment simulation.

### TABLE 6 — POOLED RETROSPECTIVE EVALUATION METRICS (EXPERIMENT B)
| Target Evaluation Slice | Test Sample Count ($N$) | MAE (mm) | RMSE (mm) | Mean Bias (mm) | Empirical Coverage (%) | Rule A F1 | Rule B F1 | Rule C F1 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Combined 3-Month Test** | 73,575 | **3.9263** | **8.7712** | +0.6138 | **88.44%** | 0.4618 | 0.5278 | 0.5279 |
| **July Test Subset** | 24,525 | 5.8053 | 12.6086 | -0.2113 | **79.52%** | 0.5145 | 0.5874 | 0.5811 |
| **August Test Subset** | 24,525 | 3.0029 | 6.3487 | +1.4648 | **94.01%** | 0.4160 | 0.4119 | 0.4106 |
| **September Test Subset** | 24,525 | 2.9705 | 5.6143 | +0.5879 | **91.78%** | 0.2637 | 0.3716 | 0.4030 |

*Observations on Pooled Training:*
- On the **July subset**, pooled training yields MAE of 5.8053 mm (vs 6.2544 mm in single-month replication) and Rule B F1 of **0.5874** (vs 0.5614).
- On the **August subset**, pooled training achieves MAE of 3.0029 mm and RMSE of 6.3487 mm (comparable to Phase 1A RMSE of 6.4008 mm). Rule B F1 is **0.4119** (vs 0.3842).
- On the **September subset**, pooled training achieves MAE of 2.9705 mm and RMSE of 5.6143 mm (comparable to single-month RMSE of 5.6328 mm).
- Combined marginal coverage of **88.44%** demonstrates that pooling multi-month data maintains empirical coverage above the nominal 80% level under the exchangeability assumption across varied synoptic backgrounds.

---

## 9. Experiment C: Retrospective Cross-Month Transfer (Leave-One-Month-Out)

Experiment C tests statistical transfer when a model is trained and calibrated strictly on two calendar months and evaluated on the held-out third month.

> **Operational Distinction:** These are retrospective cross-month transfer experiments measuring statistical transfer across calendar months. They are **NOT** operational hindcasts, as training sets may contain calendar months chronologically subsequent to the target month.

### TABLE 7 — RETROSPECTIVE CROSS-MONTH TRANSFER METRICS (EXPERIMENT C)
| Held-Out Target Month | Training & Calibration Months | Test $N$ | MAE (mm) | RMSE (mm) | Empirical Coverage (%) | Rule A F1 | Rule B F1 | Rule C F1 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **July 2023** | August + September | 24,525 | 5.7820 | 12.9710 | **75.79%** | 0.5068 | 0.5804 | 0.5837 |
| **August 2023** | July + September | 24,525 | 3.9334 | 7.0500 | **88.69%** | 0.4293 | 0.3870 | 0.3744 |
| **September 2023** | July + August | 24,525 | 3.2930 | 5.9775 | **91.82%** | 0.2472 | 0.3444 | 0.3569 |

*Cross-Month Transfer Findings:*
1. **Case 1 (Hold Out July):** Training on drier months (Aug+Sept) and evaluating on peak monsoon (July) achieves MAE of 5.7820 mm and Rule B F1 of 0.5804. Empirical coverage (75.79%) falls slightly below the nominal 80% level, as calibration intervals formed during drier months are narrower than the higher-variance July regime requires.
2. **Case 2 (Hold Out August):** Training on July+Sept and evaluating on August achieves MAE of 3.9334 mm, RMSE of 7.0500 mm, and empirical coverage of 88.69%. Rule A F1 reaches **0.4293**.
3. **Case 3 (Hold Out September):** Training on July+Aug and evaluating on September achieves MAE of 3.2930 mm and RMSE of 5.9775 mm with empirical coverage of 91.82%.

---

## 10. Stability and Variability Analysis

| Metric / Dimension | Stability Assessment | Measured Evidence across July, August, September |
| :--- | :--- | :--- |
| **Marginal Conformal Coverage** | **Consistent Adherence** | Empirical coverage remains between **84.25% and 91.04%** in single-month replication and **88.44%** in pooled evaluation against the nominal 80% target under the exchangeability assumption. |
| **Intermediate Bust Prevalence (25–50 mm)** | **Empirically Consistent** | In the 25–50 mm observed rainfall regime, bust prevalence is approximately: **36.68% (July), 35.13% (August), 36.83% (September)**. |
| **Regression Improvements** | **Consistently Observed** | MAE improvement ranges from **+12.68% to +36.80%**; RMSE improvement ranges from **+24.01% to +34.11%**. |
| **Absolute Error Magnitude** | **Synoptically Variable** | Test MAE ranges from 2.67 mm (August break spell) to 6.25 mm (July active spell), reflecting the physical scale of precipitation. |
| **Bust Rule Recall** | **Prevalence-Dependent** | Rule A recall ranges from 15.98% (September, low prevalence) to 40.59% (July, high prevalence). Precision remains high throughout (58.33% to 92.38%). |

---

## 11. Scientific Limitations

1. **Research Proxy Status:** NOAA GFS 0.25° is an open-data research proxy. Performance numbers reflect GFS error characteristics and do not represent NCMRWF operational NCUM-G model verification.
2. **D+1 Accumulation Horizon:** Verification covers 24-hour accumulations from Day 0 03:00 UTC to Day +1 03:00 UTC. Multi-day forecast degradation at D+2 through D+5 remains unquantified.
3. **Conditional Subgroup Coverage:** Conformal guarantees apply marginally under the exchangeability assumption across the full test distribution. Subgroup coverage on post-hoc bust cases ($|F - O| > 25\text{ mm}$) is not guaranteed by the marginal conformal guarantee, resulting in lower empirical subgroup coverage (8.30% to 40.59%) on extreme tail events.
4. **Heuristic Nature of Alert Scores:** The `derived_bust_risk_score` is a continuous model-based risk indicator scaled in $[0, 1]$, not a calibrated Bayesian posterior probability.
5. **Observation Sparsity in Complex Terrain:** IMD 0.25° gridded rainfall is gauge-interpolated; high-altitude Himalayan and northeastern regions have sparser gauge density than peninsular and central India.

---

## 12. Conclusions Supported by Measured Results

1. **Multi-Month Replicability:** The gradient-boosted error architecture reduces both MAE and RMSE across all three evaluated months of the 2023 monsoon season (+12.7% to +36.8% MAE improvement).
2. **Conformal Calibration Coverage:** Split Conformal Prediction achieves empirical marginal coverage exceeding the nominal 80% threshold across single-month (84.3%–91.0%) and pooled multi-month (88.4%) settings under the exchangeability assumption.
3. **Precipitation Scaling Relation:** Forecast error and bust prevalence exhibit monotonic increases with rainfall intensity across all three months, transitioning from <4% bust prevalence under 10 mm to >74% under rain exceeding 50 mm.
4. **Cross-Month Transfer Findings:** Retrospective cross-month transfer experiments show that error relationships learned across different monsoon phases retain predictive signal on held-out test partitions without catastrophic divergence, maintaining high specificity and empirical marginal coverage between 75.8% and 91.8%.
