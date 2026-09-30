# VISHWAS: Weather Intelligence & Spatiotemporal Hazard Warning Assessment System

> **MoES / NCMRWF Operational AI Prototype**  
> AI-Powered Forecast Bust Detection & Conformal Uncertainty Quantification for Numerical Weather Prediction (NCUM-G).  
> **Problem Statement 26079:** AI/ML-based Forecast Bust Detection and Reliability Assessment System for Numerical Weather Prediction Models (Ministry of Earth Sciences / National Centre for Medium Range Weather Forecasting).

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Framework: Next.js 14](https://img.shields.io/badge/Frontend-Next.js%2014%20App%20Router-black)](https://nextjs.org/)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI%20Python%203.11-009688)](https://fastapi.tiangolo.com/)
[![Map Engine: MapLibre GL](https://img.shields.io/badge/Map-MapLibre%20GL%20JS%20v6-blue)](https://maplibre.org/)
[![ML: XGBoost + MAPIE + TreeSHAP](https://img.shields.io/badge/ML-CQR%20%2B%20TreeSHAP-orange)](https://mapie.readthedocs.io/)

---

## 1. Executive Summary & Scientific Innovation

Operational Numerical Weather Prediction (NWP) models such as **NCUM-G** (National Centre for Medium Range Weather Forecasting Unified Model - Global, 12km resolution, 70 vertical levels) occasionally produce severe forecast failures known as **"forecast busts"**—episodes where deterministic precipitation diverges catastrophically from observed ground truth.

**VISHWAS** is an operational AI co-pilot designed for NCMRWF/MoES duty meteorologists and disaster management authorities (NDRF/SDMA). Rather than blindly trusting raw NWP output, VISHWAS computes:

1. **Conformalized Forecast Reliability Field (CFRF):** Continuous spatiotemporal reliability surfaces across India and surrounding ocean basins (0.0 to 1.0 bust probability) for forecast lead times Day 1 (24h) through Day 10 (240h).
2. **Mathematically Guaranteed Uncertainty Bounds (CQR):** Conformalized Quantile Regression (via MAPIE) providing rigorous 80% coverage intervals (`+45mm to +78mm`) that are finite-sample distribution-free.
3. **Linguistic TreeSHAP Attribution:** Converts complex Shapley additive explanation vectors into actionable meteorological physical drivers (e.g. *“Anomalous CAPE exceeding convective limits (> 3800 J/kg)”*, *“Ensemble spread divergence”*).
4. **Fractions Skill Score (FSS) Spatial Verification:** Recharts-based spatial decay curve tracking precipitation skill against the operational $FSS \ge 0.5$ predictability horizon limit.
5. **Historical Analog Matching:** Identifies past historical bust low-pressure systems with top meteorological similarities and verified outcome distributions.

---

## 2. System Architecture & Repository Structure

```
SIH/
├── backend/
│   ├── data/                   # 10 precomputed GeoJSON grids (1x1 deg India basin)
│   ├── main.py                 # FastAPI operational server & REST contracts
│   ├── test_api.py             # FastAPI TestClient unit test suite
│   └── requirements.txt        # Backend Python dependencies
├── ml_pipeline/
│   ├── generate_mock_data.py   # Deterministic NCUM-G scenario synthesizer
│   ├── train_pipeline.py       # XGBoost + MAPIE CQR + TreeSHAP training & validation
│   └── ml_validation.json      # Offline ML test set calibration & coverage metrics
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # Unified SPA state coordinator
│   │   ├── layout.tsx          # Root layout & dark mission theme
│   │   └── globals.css         # Tailwind & mission HUD styles
│   ├── components/
│   │   ├── Header.tsx          # NCMRWF agency context, UTC/IST clocks, telemetry pill
│   │   ├── MapContainer.tsx    # MapLibre GL JS engine with ESRI Dark Canvas & CFRF layer
│   │   ├── TimelineOverlay.tsx # D+1 to D+10 scrubber, auto-play, D+5 critical marker
│   │   ├── GlobalMetricsPanel.tsx # Network FCI, distribution histogram, Confidence DNA
│   │   ├── RegionInspector.tsx # FCI gauge, CQR bounds, TreeSHAP drivers, FSS decay curve
│   │   └── SystemStatusModal.tsx # Telemetry health inspection modal
│   ├── public/
│   │   ├── maplibre-gl-worker.mjs # Standalone MapLibre v6 Web Worker
│   │   └── maplibre-gl-shared.mjs # Shared Web Worker chunk
│   └── package.json            # Next.js 14, Recharts, Lucide, MapLibre
├── docs/
│   ├── VISHWAS_RESEARCH_AND_PRODUCT_SPEC.md # Authoritative research specification
│   ├── API_KEYS_AND_ENVIRONMENT.md          # Environment variable & credential inventory
│   └── IMPLEMENTATION_STATUS_REPORT.md      # Detailed release readiness report
├── screenshots/                # Playwright E2E validation captures
├── Dockerfile.backend          # Production container for FastAPI & ML engine
├── Dockerfile.frontend         # Multi-stage production container for Next.js UI
├── docker-compose.yml          # Container orchestration configuration
├── verify_backend.py           # Standalone automated backend endpoint verifier
├── test_e2e.py                 # Automated Playwright E2E test suite
├── .env.example                # Environment configuration template
└── README.md
```

---

## 3. Environment Variables & Credentials

> **Zero Credentials Required for Local Evaluation:**  
> The VISHWAS local prototype requires **no API keys, tokens, or external credentials**. The MapLibre engine loads the public ESRI Dark Gray Canvas basemap directly over HTTPS. All forecast grids are precomputed and served locally.

For custom port configurations or production environment templates, see:
👉 **[docs/API_KEYS_AND_ENVIRONMENT.md](docs/API_KEYS_AND_ENVIRONMENT.md)**

```bash
# Optional: copy configuration template
cp .env.example .env.local
```

---

## 4. Quick Start: Local Execution

### Prerequisites
- Python 3.10+ (Python 3.11 tested)
- Node.js 18+ or 20+
- Modern Web Browser (Chrome, Chromium, Edge, Firefox)

### Step 1: Backend Setup
```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Run backend server on port 8000
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
- Swagger API Documentation: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/healthz`
- Operational Telemetry: `http://127.0.0.1:8000/api/v1/status`

### Step 2: Frontend Setup
```bash
# In a new terminal, navigate to frontend
cd frontend
npm install --legacy-peer-deps

# Run production build or development server
npm run build
npm run start -p 3000
# or for hot-reloading dev mode:
# npm run dev
```
Open **`http://localhost:3000`** in your browser.

---

## 5. Machine Learning & Data Pipeline Execution

To regenerate the 10-day gridded forecast scenarios or retrain the XGBoost + MAPIE CQR conformal pipeline:

```bash
# 1. Synthesize 10-day gridded GeoJSON forecast scenario (lon 68-97, lat 8-35)
python ml_pipeline/generate_mock_data.py

# 2. Train XGBoost regressor, fit MAPIE CQR (80% coverage), and compute TreeSHAP
python ml_pipeline/train_pipeline.py
```
Validation checkpoints and empirical coverage intervals are saved to `ml_pipeline/ml_validation.json`.

---

## 6. Verification & Automated Testing

VISHWAS includes three dedicated automated test suites:

### 1. Backend Route Unit Tests (Pytest + FastAPI TestClient)
```bash
python -m pytest backend/test_api.py -v
```
*Validates `/healthz`, `/api/v1/status`, grid queries, point inspection, TreeSHAP explanation, and alerts.*

### 2. Standalone Backend Live Endpoint Verification
```bash
python verify_backend.py
```
*Runs live HTTP requests against all running backend endpoints and confirms response schemas.*

### 3. Frontend TypeScript & Linting
```bash
cd frontend
npm run lint
npx tsc --noEmit
```

### 4. End-to-End User Journey Tests (Playwright)
```bash
# Ensure both backend (:8000) and frontend (:3000) are running
python test_e2e.py
```
*Executes the complete 13-stage evaluator journey in headless Chromium, capturing full-resolution verification screenshots to `screenshots/`.*

---

## 7. Running with Docker Compose

To run the containerized application stack:

```bash
docker compose up --build
```
- **Frontend Dashboard:** `http://localhost:3000`
- **Backend API:** `http://localhost:8000`

---

## 8. Live Demo Script (3.5-Minute Evaluator Walkthrough)

Follow this sequence to demonstrate VISHWAS to evaluators:

### 1. Synoptic Baseline (0:00 - 0:45)
- Open `http://localhost:3000`.
- Highlight the **Mission Control Header**: NCMRWF / MoES agency badge, active assimilation cycle (`NCUM-G 12km 70L, 00Z Cycle`), live synchronized **UTC and IST clocks**, and the **Coverage: 80% CQR Bound** indicator.
- Note the **Operations Overview** panel on the left: Network Mean FCI is nominal (~67.3/100, Synoptic Baseline), and 72% of grid cells exhibit nominal error behavior.
- Point out the **Confidence DNA Barcode** for monitored zones, showing multi-day forecast stability.

### 2. Timeline Scrubbing to Day 5 (0:45 - 1:30)
- In the bottom timeline HUD, click the **Play** button or click directly on the glowing **D+5 (CRITICAL)** tick.
- The map transitions to the 120-hour horizon. The banner activates: **DEMO HOTSPOT: ODISHA BUST EPISODE**.
- Point out the **CFRF Heatmap**: A severe forecast bust zone emerges over the Bay of Bengal and coastal Odisha, glowing in crimson (`bust_prob > 0.85`).
- The Left Panel updates dynamically: Mean Network FCI drops, and the Odisha Coastal Plain card reflects a 94% bust probability.

### 3. Region Inspector & Mathematical Guarantees (1:30 - 2:30)
- Click on the **Odisha Coastal Plain & Offshore** alert card (or click directly on cell `[20.0°N, 85.0°E]`).
- The map glides to the Odisha coast with a cyan border highlighting the inspected 1x1 degree cell.
- The **Region Inspector** opens on the right:
  - **FCI Gauge:** Drops to **11.6 / 100 (Severe Forecast Bust)**.
  - **80% CQR Error Bound:** Mathematically proven conformal interval: deterministic NCUM precipitation is **48.5 mm/day**, but actual rainfall will diverge by **+49.1mm to +93.9mm**.
  - **Physical Bust Attribution (TreeSHAP):** Shows translated meteorological drivers:
    1. *Anomalous CAPE exceeding convective limits (> 3800 J/kg)*
    2. *Extreme ensemble divergence indicating unpredictable synoptic flow*
    3. *Rapidly deepening upper-level trough with intense diabatic feedback*
  - **Spatial Verification (FSS Decay):** Demonstrates that spatial predictability drops below the operational $FSS = 0.5$ limit at **Day 4**, proving deterministic guidance on Day 5 is physically unreliable.

### 4. Historical Analogs & Telemetry Health (2:30 - 3:30)
- In the inspector, toggle the **HISTORICAL ANALOGS** tab.
- Review matched historical low-pressure events (e.g. *2020 Bay of Bengal Monsoon Low - 94% similarity, +52mm bust error*).
- Click the **STATUS: OPERATIONAL** telemetry pill in the header to view the full pipeline specification.

---

## 9. Scientific Integrity & Prototype Honesty Disclosures

In accordance with scientific and product honesty:
- **Synthetic Demonstration Scenarios:** The 10-day gridded numerical data used in this prototype is synthetically generated via `ml_pipeline/generate_mock_data.py`. The meteorological relationships (CAPE thresholds, monsoon troughs, and ensemble divergence) emulate physical NWP characteristics but **do not represent live operational MoES/NCMRWF supercomputer data streams**.
- **Stand-alone Operation:** External government supercomputing feeds (NCUM GRIB2 streams) and IMD Doppler Weather Radar feeds are simulated through the mock generator to guarantee 100% reliability, zero latency, and zero air-gapped network dependencies during evaluation.
- **Conformal Guarantees:** The CQR prediction intervals are computed via MAPIE conformalized quantile regression; the mathematical 80% coverage guarantees apply rigorously under exchangeability of the calibration and test distributions.

---

## 10. Authoritative Research Specification

For complete mathematical formulations, conformal coverage equations, and NCUM-G assimilation physics, see:  
👉 **[docs/VISHWAS_RESEARCH_AND_PRODUCT_SPEC.md](docs/VISHWAS_RESEARCH_AND_PRODUCT_SPEC.md)**
