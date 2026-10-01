"use client";

import React, { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import { Header } from "../components/Header";
import { TimelineOverlay } from "../components/TimelineOverlay";
import { RegionInspector } from "../components/RegionInspector";
import { GlobalMetricsPanel } from "../components/GlobalMetricsPanel";
import { SystemStatusModal } from "../components/SystemStatusModal";

const MapContainer = dynamic(
  () => import("../components/MapContainer").then((mod) => mod.MapContainer),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex flex-col items-center justify-center bg-slate-950 font-mono text-xs text-slate-400 gap-2">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <span>INITIALIZING MAPLIBRE WEBGL CONTEXT...</span>
      </div>
    ),
  }
);
import {
  GridProperties,
  ForecastGridGeoJSON,
  AlertZoneItem,
  SystemStatusData,
  PointDetailsResponse,
} from "../types/forecast";

const API_BASE = "";

export default function Home() {
  // Default to REAL mode as the primary VISHWAS product experience
  // Explicit ?mode=demo switches to synthetic DEMO mode
  const [isRealMode, setIsRealMode] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      const param = new URLSearchParams(window.location.search).get("mode");
      if (param) return param.toLowerCase() !== "demo";
    }
    const env = (process.env.NEXT_PUBLIC_DATA_MODE || "").toUpperCase();
    if (env === "DEMO") return false;
    return true; // Default to REAL mode
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      const param = new URLSearchParams(window.location.search).get("mode");
      if (param) {
        setIsRealMode(param.toLowerCase() !== "demo");
      }
    }
  }, []);

  const handleToggleMode = useCallback(() => {
    setIsRealMode((prev) => {
      const next = !prev;
      if (typeof window !== "undefined") {
        const url = new URL(window.location.href);
        url.searchParams.set("mode", next ? "real" : "demo");
        window.history.replaceState({}, "", url.toString());
      }
      return next;
    });
  }, []);

  const [leadTime, setLeadTime] = useState<number>(1);
  const [gridData, setGridData] = useState<ForecastGridGeoJSON | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [systemError, setSystemError] = useState<string | null>(null);

  // Inspector & Selection State
  const [selectedRegion, setSelectedRegion] = useState<GridProperties | null>(null);
  const [pointDetails, setPointDetails] = useState<PointDetailsResponse | null>(null);

  // Global Alerts & System Status
  const [alerts, setAlerts] = useState<AlertZoneItem[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatusData | null>(null);
  const [isStatusModalOpen, setIsStatusModalOpen] = useState<boolean>(false);

  // FlyTo animation target
  const [flyToLocation, setFlyToLocation] = useState<{ lon: number; lat: number; zoom?: number } | null>(null);

  // 1. Fetch grid data on lead time change
  const fetchGridData = useCallback(async (lt: number) => {
    // In REAL mode, D10 is unavailable
    if (isRealMode && lt > 9) {
      console.warn("D+10 is not available in REAL validation mode.");
      return;
    }
    setIsLoading(true);
    try {
      const modeParam = isRealMode ? "&mode=real" : "";
      const res = await fetch(`${API_BASE}/api/v1/forecast/grid?lead_time=${lt}${modeParam}`);
      if (!res.ok) {
        if (res.status === 422 && isRealMode && lt === 10) {
          throw new Error("D+10 is not empirically available in the current REAL validation dataset.");
        }
        throw new Error(`HTTP error ${res.status}`);
      }
      const data: ForecastGridGeoJSON = await res.json();
      setGridData(data);
      setSystemError(null);

      // If an existing cell was selected, update its properties for the new lead time
      setSelectedRegion((prev) => {
        if (!prev) return null;
        const matching = data.features.find(
          (f) => f.properties.grid_id === prev.grid_id
        );
        return matching ? matching.properties : prev;
      });
    } catch (err: unknown) {
      console.error("Failed to load forecast grid:", err);
      setSystemError(err instanceof Error ? err.message : "Failed to reach backend");
    } finally {
      setIsLoading(false);
    }
  }, [isRealMode]);

  // 2. Fetch point details when cell is selected
  const fetchPointDetails = useCallback(async (lat: number, lon: number, lt: number) => {
    if (isRealMode && lt > 9) return;
    try {
      const modeParam = isRealMode ? "&mode=real" : "";
      const res = await fetch(`${API_BASE}/api/v1/forecast/point?lat=${lat}&lon=${lon}&lead_time=${lt}${modeParam}`);
      if (res.ok) {
        const data: PointDetailsResponse = await res.json();
        setPointDetails(data);
        if (data.properties) {
          setSelectedRegion(data.properties);
        }
      }
    } catch (err) {
      console.warn("Could not fetch detailed point timeseries:", err);
    }
  }, [isRealMode]);

  // 3. Initial load of alerts and telemetry status with mode awareness
  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const modeParam = isRealMode ? "?mode=real" : "";
        const [alertsRes, statusRes] = await Promise.all([
          fetch(`${API_BASE}/api/v1/alerts${modeParam}`),
          fetch(`${API_BASE}/api/v1/status${modeParam}`),
        ]);

        if (alertsRes.ok) {
          const alertsData = await alertsRes.json();
          setAlerts(alertsData);
        }
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          setSystemStatus(statusData);
        }
      } catch (err: unknown) {
        console.warn("Initial metadata fetch error:", err);
      }
    };

    fetchMetadata();
  }, [isRealMode]);

  // Trigger grid fetch on lead time change
  useEffect(() => {
    fetchGridData(leadTime);
  }, [leadTime, fetchGridData]);

  // When a map cell is clicked
  const handleSelectCell = useCallback(
    (props: GridProperties) => {
      setSelectedRegion(props);
      fetchPointDetails(props.lat, props.lon, leadTime);
    },
    [leadTime, fetchPointDetails]
  );

  // When an alert card is clicked from GlobalMetricsPanel
  const handleSelectAlert = useCallback(
    (alert: AlertZoneItem) => {
      const targetLead = isRealMode ? Math.min(alert.lead_time, 9) : alert.lead_time;
      setLeadTime(targetLead);
      setFlyToLocation({ lon: alert.lon, lat: alert.lat, zoom: 6.0 });

      // In real mode, use clean properties from alert without synthetic cyclone mock
      const alertProps: GridProperties = {
        grid_id: alert.id,
        lon: alert.lon,
        lat: alert.lat,
        lead_time: targetLead,
        lead_time_str: `D+${targetLead}`,
        region_name: alert.region_name,
        f_precip: isRealMode ? 2.5 : 48.5,
        bust_prob: alert.bust_prob,
        fci: alert.fci,
        cqr_bounds: alert.cqr_bounds,
        cqr_lower: 0.0,
        cqr_upper: 9.0,
        expected_error_median: 2.5,
        interval_width: 9.0,
        cape: isRealMode ? 350 : 3950,
        ensemble_spread: isRealMode ? 2.25 : 9.2,
        z500_gradient: isRealMode ? 58.0 : 42.0,
        wind_shear: isRealMode ? 12.0 : 28.0,
        fss_horizon_day: isRealMode ? 6 : 4,
        shap_drivers: [
          alert.primary_driver,
          isRealMode
            ? "Regional baseline forecast uncertainty from latitudinal circulation"
            : "Extreme ensemble divergence indicating unpredictable synoptic flow",
        ],
      };
      setSelectedRegion(alertProps);
      fetchPointDetails(alert.lat, alert.lon, targetLead);
    },
    [isRealMode, fetchPointDetails]
  );

  const handleLeadTimeChange = useCallback((newLead: number) => {
    if (isRealMode && newLead > 9) {
      console.warn("D+10 is unavailable in REAL mode.");
      return;
    }
    setLeadTime(newLead);
  }, [isRealMode]);

  return (
    <div className="relative w-screen h-screen flex flex-col bg-slate-900 text-slate-200 overflow-hidden select-none">
      {/* Top Header */}
      <Header
        leadTime={leadTime}
        isLoading={isLoading}
        systemError={systemError}
        onOpenStatusModal={() => setIsStatusModalOpen(true)}
        systemStatus={systemStatus}
        isRealMode={isRealMode}
        onToggleMode={handleToggleMode}
      />

      {/* Main Viewport Container */}
      <main className="relative flex-1 w-full h-full overflow-hidden">
        {/* Full-bleed interactive MapLibre map */}
        <MapContainer
          gridData={gridData}
          onSelectCell={handleSelectCell}
          selectedGridId={selectedRegion?.grid_id || null}
          flyToLocation={flyToLocation}
          isRealMode={isRealMode}
        />

        {/* Left Overlay: Operations Overview with Confidence DNA */}
        <GlobalMetricsPanel
          alerts={alerts}
          systemStatus={systemStatus}
          onSelectAlert={handleSelectAlert}
          selectedAlertId={selectedRegion?.grid_id || null}
          currentLeadTime={leadTime}
          isInspectorOpen={!!selectedRegion}
          isRealMode={isRealMode}
        />

        {/* Right Overlay: Region Inspector with Conformal bounds & TreeSHAP XAI */}
        <RegionInspector
          properties={selectedRegion}
          pointDetails={pointDetails}
          onClose={() => {
            setSelectedRegion(null);
            setPointDetails(null);
          }}
          leadTime={leadTime}
          isRealMode={isRealMode}
        />

        {/* Bottom Overlay: Interactive Lead Time Scrubbing Timeline */}
        <TimelineOverlay
          leadTime={leadTime}
          onLeadTimeChange={handleLeadTimeChange}
          isLoading={isLoading}
          isInspectorOpen={!!selectedRegion}
          isRealMode={isRealMode}
        />
      </main>

      {/* Telemetry & Pipeline Health Modal */}
      <SystemStatusModal
        isOpen={isStatusModalOpen}
        onClose={() => setIsStatusModalOpen(false)}
        statusData={systemStatus}
        isRealMode={isRealMode}
      />
    </div>
  );
}
