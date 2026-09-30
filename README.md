# VISHWAS: Weather Intelligence & Spatiotemporal Hazard Warning Assessment System

> **NCMRWF / MoES Operational Prototype**  
> AI-Powered Forecast Bust Detection & Conformal Uncertainty Quantification for Numerical Weather Prediction (NCUM-G).

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Framework: Next.js 14](https://img.shields.io/badge/Frontend-Next.js%2014%20App%20Router-black)](https://nextjs.org/)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI%20Python%203.11-009688)](https://fastapi.tiangolo.com/)
[![Map Engine: MapLibre GL](https://img.shields.io/badge/Map-MapLibre%20GL%20JS-blue)](https://maplibre.org/)
[![ML: XGBoost + MAPIE + TreeSHAP](https://img.shields.io/badge/ML-CQR%20%2B%20TreeSHAP-orange)](https://mapie.readthedocs.io/)

---

## 1. Executive Summary & Scientific Innovation

Operational Numerical Weather Prediction (NWP) models such as **NCUM-G** (National Centre for Medium Range Weather Forecasting Unified Model - Global, 12km resolution, 70 vertical levels) occasionally produce severe forecast failures known as **"forecast busts"**—episodes where deterministic precipitation diverges catastrophically from observed ground truth.

**VISHWAS** is an operational AI co-pilot designed for NCMRWF/MoES duty meteorologists and disaster management authorities (NDRF/SDMA). Rather than blindly trusting NWP precipitation output, VISHWAS computes:

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
│   └── VISHWAS_RESEARCH_AND_PRODUCT_SPEC.md # Authoritative research specification
├── screenshots/                # Playwright E2E validation captures
├── Dockerfile.backend          # Production container for FastAPI & ML engine
├── Dockerfile.frontend         # Multi-stage production container for Next.js UI
├── docker-compose.yml          # Container orchestration configuration
├── test_e2e.py                 # Automated Playwright test suite
└── README.md
```

---

## 3. Quick Start & Local Execution

### Prerequisites
- Python 3.10+ (Python 3.11 recommended)
- Node.js 18+ or 20+
- Modern Web Browser (Chrome / Chromium / Edge / Firefox)

### Step 1: Backend Setup & Data Generation

```bash
# Navigate to backend and install dependencies
cd backend
pip install -r requirements.txt

# (Optional) Retrain or regenerate synthetic NCUM-G scenario data
python ../ml_pipeline/generate_mock_data.py
python ../ml_pipeline/train_pipeline.py

# Start FastAPI server on port 8000
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Backend will be live at `http://127.0.0.1:8000`. You can test endpoints:
- Swagger Docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/healthz`
- Status telemetry: `http://127.0.0.1:8000/api/v1/status`
- Forecast grid (Day 5): `http://127.0.0.1:8000/api/v1/forecast/grid?lead_time=5`

### Step 2: Frontend Setup

```bash
# In a new terminal, navigate to frontend
cd frontend
npm install --legacy-peer-deps

# Run in production mode or development mode:
npm run build
npm run start -p 3000
# or: npm run dev
```
Open **`http://localhost:3000`** in your browser.

---

## 4. Running with Docker Compose

To launch the entire synchronized stack with Docker:

```bash
# From workspace root
docker compose up --build
```
- **Frontend UI:** `http://localhost:3000`
- **Backend API:** `http://localhost:8000`

---

## 5. Live Demo Script (3.5-Minute Hackathon Walkthrough)

Follow this exact walkthrough to demonstrate VISHWAS to jury members and evaluators:

### 1. Synoptic Baseline (0:00 - 0:45)
- Open `http://localhost:3000`.
- Point out the top mission bar: **NCMRWF / MoES** agency context, active model cycle (`NCUM-G 12km 70L, 00Z Cycle`), live synchronized **UTC and IST clocks**, and the **Coverage: 80% CQR Bound** indicator.
- Note the **Operations Overview** panel on the left: Network Mean FCI is healthy (~67.3/100, Synoptic Baseline), and 72% of grid cells exhibit nominal forecast error behavior.
- Show the **Confidence DNA Barcode** for the monitored zones, demonstrating 10-day stability across early lead times.

### 2. Timeline Scrubbing to Day 5 (0:45 - 1:30)
- In the bottom timeline HUD, click the **Play** button or click directly on the glowing **D+5 (CRITICAL)** tick.
- The map transitions to the 120-hour horizon. The banner turns red: **DEMO HOTSPOT: ODISHA BUST EPISODE**.
- Notice the **CFRF Heatmap**: A severe forecast bust zone emerges over the Bay of Bengal and coastal Odisha, glowing in vibrant crimson (`bust_prob > 0.85`).
- The Left Panel updates dynamically: Mean Network FCI drops, and the Odisha Coastal Plain card reflects a 94% bust probability.

### 3. Region Inspector & Mathematical Guarantees (1:30 - 2:30)
- Click on the **Odisha Coastal Plain & Offshore** alert card (or click directly on grid cell `[20.0°N, 85.0°E]` on the map).
- The map smoothly glides to the Bay of Bengal / Odisha coast with a blue border highlighting the inspected 1x1 degree cell.
- The **Region Inspector** opens on the right:
  - **FCI Gauge:** Drops to **11.6 / 100 (Severe Forecast Bust)**.
  - **80% CQR Error Bound:** Mathematically proven conformal prediction interval: deterministic NCUM precipitation is **48.5 mm/day**, but actual rainfall will diverge by **+49.1mm to +93.9mm**.
  - **Physical Bust Attribution (TreeSHAP):** Shows translated meteorological drivers:
    1. *Anomalous CAPE exceeding convective limits (> 3800 J/kg)*
    2. *Extreme ensemble divergence indicating unpredictable synoptic flow*
    3. *Rapidly deepening upper-level trough with intense diabatic feedback*
  - **Spatial Verification (FSS Decay):** Demonstrates that spatial predictability drops below the operational $FSS = 0.5$ limit at **Day 4**, meaning deterministic details on Day 5 are physically unreliable.

### 4. Historical Analogs & Telemetry Health (2:30 - 3:30)
- In the inspector, toggle the **HISTORICAL ANALOGS** tab.
- Review matched historical low-pressure events (e.g. *2020 Bay of Bengal Monsoon Low - 91% similarity, +64mm bust error*).
- Click the **STATUS: OPERATIONAL** telemetry pill in the top header.
- The modal reveals the complete technical specification: XGBoost regressor, MAPIE Conformal Quantile Regression with 80% empirical coverage, TreeSHAP explainer, and automated data ingestion health checks.

---

## 6. Verification & Automated Testing

VISHWAS includes an automated end-to-end testing suite powered by Playwright:

```bash
# Run headless browser E2E test suite
python test_e2e.py
```

The test validates:
- [x] Header branding, agency badges, model run cycle, and UTC/IST clocks.
- [x] Operations Overview metrics, cell error distributions, and Tufte Confidence DNA barcodes.
- [x] Timeline scrubbing from D+1 to D+10 and Day 5 hotspot detection.
- [x] Map click and flyTo animations to the Odisha bust zone.
- [x] CQR conformal prediction interval bounds calculation.
- [x] Linguistic TreeSHAP physical attribution driver formatting.
- [x] FSS spatial verification decay curve with 0.5 threshold line.
- [x] Historical analog matching view.
- [x] System telemetry status modal inspection.
- [x] Zero browser console errors.

Screenshots of the verified operational run are preserved in `screenshots/`.

---

## 7. Authoritative Specifications

For complete scientific derivations, conformal coverage equations, NCUM-G assimilation physics, and product UX rationale, consult:

👉 **[docs/VISHWAS_RESEARCH_AND_PRODUCT_SPEC.md](file:///c:/builds/SIH/docs/VISHWAS_RESEARCH_AND_PRODUCT_SPEC.md)**
