# VISHWAS: API Keys, Credentials, and Environment Configuration Inventory

This document provides a comprehensive inventory of all environment variables, API keys, tokens, credentials, external services, and network dependencies across the **VISHWAS** system.

---

## 1. Summary Matrix

| Variable / Credential | Required? | Used By | Purpose | Where to Obtain | Needed for Local Demo? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | **No** (Defaults to `http://127.0.0.1:8000`) | Frontend (`next.config.mjs`, Docker Compose) | Specifies the base URL of the FastAPI backend for client API rewrites. | Configured locally by developer / container orchestrator. | **No** (Optional override) |
| `PORT` (Frontend) | **No** (Defaults to `3000`) | Next.js server runtime (`Dockerfile.frontend`) | HTTP listen port for the Next.js server. | Set in system environment or Dockerfile. | **No** (Defaults to 3000) |
| `PORT` (Backend) | **No** (Defaults to `8000`) | Uvicorn ASGI server (`docker-compose.yml`) | HTTP listen port for the FastAPI server. | Set in system environment or Dockerfile. | **No** (Defaults to 8000) |
| `MAPLIBRE_TILES_URL` / Carto / MapTiler API Key | **No** | Frontend (`MapContainer.tsx`) | Vector or raster basemap tile source. | Public ESRI World Dark Gray Canvas is used by default (zero key required). | **No** |
| `NCMRWF_GRIB_FTP_CREDENTIALS` | **No** (Production only) | Operational Ingestion Pipeline | Automated ingestion of live operational NCUM-G (12km) GRIB2/NetCDF forecast model output streams. | MoES / NCMRWF IT & HPC Division (MoES operational networks). | **No** (Simulated in prototype) |
| `IMD_AWS_RADAR_API_KEY` | **No** (Production only) | Ground Truth Verification Pipeline | Ingestion of live IMD Doppler Weather Radar (DWR) quantitative precipitation estimates and rain-gauge networks. | India Meteorological Department (IMD) Data Supply Portal. | **No** (Simulated in prototype) |
| `POSTGRES_DB_URL` / PostGIS | **No** (Production only) | Persistent Spatiotemporal Store | Relational and spatial querying for multi-year historical forecast bust logs and verification archive. | Self-hosted PostgreSQL/PostGIS or Managed RDS/Cloud SQL. | **No** (Static GeoJSON used for prototype) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / S3 | **No** (Production only) | Cloud Archive / Model Artifacts | Object storage for trained XGBoost models, MAPIE calibration checkpoints, and daily GeoJSON archives. | Cloud infrastructure provider (AWS / MeitY-empaneled Gov Cloud). | **No** (Local filesystem used) |
| `SENTRY_DSN` | **No** (Production only) | Telemetry & Observability | Application performance monitoring, uncaught error tracking, and uptime alerting. | Sentry.io or self-hosted GlitchTip. | **No** |

---

## 2. Categorized Breakdown

### A. Required for Local Prototype
> **None.**  
> The VISHWAS local prototype has been specifically engineered to operate with **zero required external credentials, zero API keys, and zero cloud service dependencies**. All forecast grids (10 lead times across the Indian subcontinent) are precomputed and cached in-memory by FastAPI, and basemap tiles are streamed from a public, keyless ESRI canvas endpoint.

---

### B. Optional for Local Prototype

#### `NEXT_PUBLIC_API_URL`
- **Consumed in:** `frontend/next.config.mjs`
- **Default Value:** `http://127.0.0.1:8000`
- **Usage:** In local development, the Next.js rewrite engine proxies `/api/v1/:path*` to `http://127.0.0.1:8000/api/v1/:path*`.
- **When to change:** If running FastAPI on a custom port, a remote staging server, or inside a custom Docker network where the service hostname is `backend:8000`.

#### `PORT`
- **Consumed in:** `Dockerfile.frontend`, `docker-compose.yml`, `backend/main.py`
- **Default Value:** `3000` (frontend), `8000` (backend)
- **Usage:** Controls local bind port for uvicorn and next start.

---

### C. Required Only for Production / Operational Deployment

The following credentials and configurations are necessary only when transitioning VISHWAS from a hackathon evaluation prototype to operational NCMRWF / MoES data centre infrastructure:

#### 1. `NCMRWF_GRIB_DATA_STREAM` (FTP/SFTP/S3)
- **Purpose:** Ingestion of operational NCUM-G raw forecasts every 6 or 12 hours (00Z, 06Z, 12Z, 18Z cycles) directly from NCMRWF Mihir/Pratyush supercomputing clusters.
- **Consumption:** Background ETL cron worker replacing `ml_pipeline/generate_mock_data.py`.
- **Source:** NCMRWF High Performance Computing division.

#### 2. `IMD_OBSERVATION_STREAM`
- **Purpose:** Daily rainfall ground-truth observations (IMD gridded rainfall analysis at 0.25° or AWS automated weather station networks) for real-time verification and continuous MAPIE CQR re-calibration.
- **Source:** National Data Centre, IMD Pune.

#### 3. `DATABASE_URL` (PostgreSQL / PostGIS)
- **Purpose:** Production persistent database for 10-year historical analog indexing, spatial spatial joins, and multi-tenant disaster agency access.
- **Format:** `postgresql://vishwas_user:secure_password@postgres:5432/vishwas_operational`

#### 4. `MAP_TILES_PROVIDER_KEY` (Optional)
- **Purpose:** High-resolution enterprise vector basemap tile services (e.g. MapTiler Server, OpenMapTiles, or Mapbox) if deploying to an air-gapped intranet where public ESRI Dark Canvas raster tiles cannot be reached over the internet.
- **Source:** Self-hosted tile server or commercial API plan.

---

### D. Not Currently Required (Prototype Uses Simulated/Static Data)

Per Parts 21 and 27 of `docs/VISHWAS_RESEARCH_AND_PRODUCT_SPEC.md`:
> *"Do not build user authentication. Do not build a live PostgreSQL/PostGIS database. Use the static GeoJSON files generated by the Python script to ensure 100% uptime during the hackathon demonstration."*

Accordingly, the following dependencies are deliberately avoided in the prototype:
1. **User Authentication & JWT Tokens:** Not required for the operational evaluation prototype.
2. **Third-party Weather APIs (e.g. OpenWeatherMap, WeatherAPI):** Strictly avoided; VISHWAS is built specifically for Indian sovereign meteorological infrastructure (NCUM-G model verification), not generic consumer weather APIs.
3. **External Tile Provider Keys:** Avoided; MapLibre GL JS loads the ESRI Dark Gray Canvas basemap directly via HTTPS tile URLs with no tokens, watermark, or rate-limiting.
