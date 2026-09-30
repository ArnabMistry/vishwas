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
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/forecast/grid?lead_time=${lt}`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
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
  }, []);

  // 2. Fetch point details when cell is selected
  const fetchPointDetails = useCallback(async (lat: number, lon: number, lt: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/forecast/point?lat=${lat}&lon=${lon}&lead_time=${lt}`);
      if (res.ok) {
        const data: PointDetailsResponse = await res.json();
        setPointDetails(data);
      }
    } catch (err) {
      console.warn("Could not fetch detailed point timeseries:", err);
    }
  }, []);

  // 3. Initial load of alerts and telemetry status
  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const [alertsRes, statusRes] = await Promise.all([
          fetch(`${API_BASE}/api/v1/alerts`),
          fetch(`${API_BASE}/api/v1/status`),
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
  }, []);

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
      // Switch timeline to the alert's peak lead time (e.g. Day 5 for Odisha)
      setLeadTime(alert.lead_time);
      setFlyToLocation({ lon: alert.lon, lat: alert.lat, zoom: 6.0 });

      // Build simulated immediate properties so Inspector opens seamlessly
      const alertProps: GridProperties = {
        grid_id: alert.id,
        lon: alert.lon,
        lat: alert.lat,
        lead_time: alert.lead_time,
        lead_time_str: alert.lead_time_str,
        region_name: alert.region_name,
        f_precip: 48.5,
        bust_prob: alert.bust_prob,
        fci: alert.fci,
        cqr_bounds: alert.cqr_bounds,
        cqr_lower: 45.0,
        cqr_upper: 78.0,
        expected_error_median: 61.5,
        interval_width: 33.0,
        cape: 3950,
        ensemble_spread: 9.2,
        z500_gradient: 42.0,
        wind_shear: 28.0,
        fss_horizon_day: 4,
        shap_drivers: [
          alert.primary_driver,
          "Extreme ensemble divergence indicating unpredictable synoptic flow",
          "Rapidly deepening upper-level trough with intense diabatic feedback",
        ],
      };
      setSelectedRegion(alertProps);
      fetchPointDetails(alert.lat, alert.lon, alert.lead_time);
    },
    [fetchPointDetails]
  );

  return (
    <div className="relative w-screen h-screen flex flex-col bg-slate-900 text-slate-200 overflow-hidden select-none">
      {/* Top Header */}
      <Header
        leadTime={leadTime}
        isLoading={isLoading}
        systemError={systemError}
        onOpenStatusModal={() => setIsStatusModalOpen(true)}
        systemStatus={systemStatus}
      />

      {/* Main Viewport Container */}
      <main className="relative flex-1 w-full h-full overflow-hidden">
        {/* Full-bleed interactive MapLibre map */}
        <MapContainer
          gridData={gridData}
          onSelectCell={handleSelectCell}
          selectedGridId={selectedRegion?.grid_id || null}
          flyToLocation={flyToLocation}
        />

        {/* Left Overlay: Operations Overview with Confidence DNA */}
        <GlobalMetricsPanel
          alerts={alerts}
          systemStatus={systemStatus}
          onSelectAlert={handleSelectAlert}
          selectedAlertId={selectedRegion?.grid_id || null}
          currentLeadTime={leadTime}
        />

        {/* Right Overlay: Region Inspector with CQR bounds & TreeSHAP XAI */}
        <RegionInspector
          properties={selectedRegion}
          pointDetails={pointDetails}
          onClose={() => {
            setSelectedRegion(null);
            setPointDetails(null);
          }}
          leadTime={leadTime}
        />

        {/* Bottom Overlay: Interactive Lead Time Scrubbing Timeline */}
        <TimelineOverlay
          leadTime={leadTime}
          onLeadTimeChange={(newLead) => setLeadTime(newLead)}
          isLoading={isLoading}
          isInspectorOpen={!!selectedRegion}
        />
      </main>

      {/* Telemetry & Pipeline Health Modal */}
      <SystemStatusModal
        isOpen={isStatusModalOpen}
        onClose={() => setIsStatusModalOpen(false)}
        statusData={systemStatus}
      />
    </div>
  );
}
