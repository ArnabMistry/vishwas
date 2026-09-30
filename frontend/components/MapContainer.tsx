"use client";

import React, { useRef, useState, useCallback, useMemo, useEffect } from "react";
import Map, { Source, Layer, MapRef, NavigationControl, LayerProps } from "react-map-gl/maplibre";
import * as maplibregl from "maplibre-gl";
import { GridProperties, ForecastGridGeoJSON } from "../types/forecast";

if (typeof window !== "undefined") {
  maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
}

interface MapContainerProps {
  gridData: ForecastGridGeoJSON | null;
  onSelectCell: (properties: GridProperties) => void;
  selectedGridId: string | null;
  flyToLocation: { lon: number; lat: number; zoom?: number } | null;
}

// ESRI World Dark Gray Canvas basemap - 100% reliable, zero watermark, zero API key required
const darkMapStyle: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    "esri-dark": {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      attribution: "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ",
    },
  },
  layers: [
    {
      id: "esri-dark-layer",
      type: "raster",
      source: "esri-dark",
      minzoom: 0,
      maxzoom: 16,
    },
  ],
};

export const MapContainer: React.FC<MapContainerProps> = ({
  gridData,
  onSelectCell,
  selectedGridId,
  flyToLocation,
}) => {
  const mapRef = useRef<MapRef | null>(null);
  const [hoverInfo, setHoverInfo] = useState<{
    x: number;
    y: number;
    properties: GridProperties;
  } | null>(null);
  const [cursor, setCursor] = useState<string>("auto");

  // Handle external flyTo trigger (e.g. from GlobalMetricsPanel alert click)
  useEffect(() => {
    if (flyToLocation && mapRef.current) {
      mapRef.current.flyTo({
        center: [flyToLocation.lon, flyToLocation.lat],
        zoom: flyToLocation.zoom || 5.8,
        duration: 1200,
        essential: true,
      });
    }
  }, [flyToLocation]);

  // Click handler
  const handleClick = useCallback(
    (event: { features?: Array<{ properties?: Record<string, unknown> }> }) => {
      const feature = event.features && event.features[0];
      if (feature && feature.properties) {
        const props = feature.properties as unknown as GridProperties;
        // Parse shap_drivers if it was stringified by geojson serialization
        const rawDrivers: unknown = props.shap_drivers;
        let parsedDrivers: string[] = [];
        if (typeof rawDrivers === "string") {
          try {
            const parsed = JSON.parse(rawDrivers);
            parsedDrivers = Array.isArray(parsed) ? parsed : [String(parsed)];
          } catch {
            parsedDrivers = [rawDrivers];
          }
        } else if (Array.isArray(rawDrivers)) {
          parsedDrivers = rawDrivers as string[];
        } else if (rawDrivers) {
          parsedDrivers = [String(rawDrivers)];
        }
        onSelectCell({
          ...props,
          shap_drivers: parsedDrivers,
        });

        // Center on clicked cell
        if (mapRef.current && props.lon && props.lat) {
          mapRef.current.easeTo({
            center: [props.lon, props.lat],
            duration: 600,
          });
        }
      }
    },
    [onSelectCell]
  );

  // Hover handler
  const handleMouseMove = useCallback(
    (event: { features?: Array<{ properties?: Record<string, unknown> }>; point: { x: number; y: number } }) => {
      const { features, point } = event;
      const hoveredFeature = features && features[0];
      if (hoveredFeature && hoveredFeature.properties) {
        setCursor("pointer");
        setHoverInfo({
          x: point.x,
          y: point.y,
          properties: hoveredFeature.properties as unknown as GridProperties,
        });
      } else {
        setCursor("auto");
        setHoverInfo(null);
      }
    },
    []
  );

  const handleMouseLeave = useCallback(() => {
    setCursor("auto");
    setHoverInfo(null);
  }, []);

  // MapLibre Fill Layer for Conformalized Forecast Reliability Field (CFRF)
  const fillLayerStyle: LayerProps = useMemo(
    () => ({
      id: "bust-layer",
      type: "fill",
      source: "forecast-grid",
      paint: {
        "fill-color": [
          "interpolate",
          ["linear"],
          ["get", "bust_prob"],
          0.0, "#10233D", // Subtle deep navy for nominal/stable forecast
          0.30, "#0284C7", // Sky blue for moderate variance
          0.60, "#F59E0B", // Amber warning
          0.80, "#E11D48", // Rose severe bust
          1.0, "#9F1239",  // Deep magenta extreme bust
        ],
        "fill-opacity": 0.65,
      },
    }),
    []
  );

  // Subtle grid mesh borders
  const outlineLayerStyle: LayerProps = useMemo(
    () => ({
      id: "bust-outline",
      type: "line",
      source: "forecast-grid",
      paint: {
        "line-color": "#334155",
        "line-width": 0.8,
        "line-opacity": 0.7,
      },
    }),
    []
  );

  // Highlight layer for the selected cell
  const highlightLayerStyle: LayerProps = useMemo(
    () => ({
      id: "bust-highlight",
      type: "line",
      source: "forecast-grid",
      paint: {
        "line-color": "#38BDF8",
        "line-width": 3.0,
        "line-opacity": 1.0,
      },
      filter: selectedGridId ? ["==", ["get", "grid_id"], selectedGridId] : ["==", ["get", "grid_id"], ""],
    }),
    [selectedGridId]
  );

  return (
    <div className="relative w-full h-full bg-[#080D1A] overflow-hidden">
      <Map
        ref={mapRef}
        mapLib={maplibregl}
        initialViewState={{
          longitude: 78.9629,
          latitude: 20.5937,
          zoom: 4.3,
        }}
        maxBounds={[62.0, 5.0, 100.0, 37.5]}
        minZoom={3.8}
        maxZoom={8.5}
        mapStyle={darkMapStyle}
        interactiveLayerIds={["bust-layer"]}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        cursor={cursor}
        style={{ width: "100%", height: "100%" }}
        onLoad={(e) => {
          if (typeof window !== "undefined") {
            (window as unknown as { _map: unknown })._map = e.target;
          }
        }}
      >
        <NavigationControl position="top-right" showCompass={false} />

        {/* CFRF Scientific Reliability Grid */}
        {gridData && (
          <Source id="forecast-grid" type="geojson" data={gridData}>
            <Layer {...fillLayerStyle} />
            <Layer {...outlineLayerStyle} />
          </Source>
        )}

        {/* Indian State Administrative Boundaries */}
        <Source id="india-states-source" type="geojson" data="/india_states.geojson">
          <Layer
            id="india-states-borders"
            type="line"
            paint={{
              "line-color": "#64748B",
              "line-width": 0.85,
              "line-opacity": 0.75,
              "line-dasharray": [3, 2],
            }}
          />
        </Source>

        {/* India National Boundary & Coastline (High Contrast) */}
        <Source id="india-boundary-source" type="geojson" data="/india_boundary.geojson">
          <Layer
            id="india-coast-glow"
            type="line"
            paint={{
              "line-color": "#0284C7",
              "line-width": 2.8,
              "line-opacity": 0.45,
            }}
          />
          <Layer
            id="india-boundary-line"
            type="line"
            paint={{
              "line-color": "#F1F5F9",
              "line-width": 1.5,
              "line-opacity": 0.95,
            }}
          />
        </Source>

        {/* ESRI Dark Gray Reference: Subordinate Geographic Labels & Surrounding Geography */}
        <Source
          id="esri-reference-source"
          type="raster"
          tiles={[
            "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
          ]}
          tileSize={256}
        >
          <Layer
            id="esri-reference-layer"
            type="raster"
            paint={{
              "raster-opacity": 0.85,
            }}
          />
        </Source>

        {/* Active Selection Highlight Layer */}
        {gridData && (
          <Source id="forecast-grid-highlight" type="geojson" data={gridData}>
            <Layer {...highlightLayerStyle} />
          </Source>
        )}
      </Map>

      {/* Lightweight HUD Tooltip on Hover with Boundary Clamping */}
      {hoverInfo && (
        <div
          className="pointer-events-none absolute z-40 bg-slate-950/95 border border-slate-700/90 rounded-sm p-2 shadow-2xl backdrop-blur-md text-[11px] font-mono text-slate-200"
          style={{
            left: `${Math.min(Math.max(hoverInfo.x, 150), typeof window !== "undefined" ? window.innerWidth - 240 : 800)}px`,
            top: `${hoverInfo.y < 140 ? hoverInfo.y + 24 : hoverInfo.y - 12}px`,
            transform: hoverInfo.y < 140 ? "translate(-50%, 0)" : "translate(-50%, -100%)",
          }}
        >
          <div className="flex items-center justify-between gap-3 text-slate-400 pb-1 border-b border-slate-800 text-[10px]">
            <span>[{Number(hoverInfo.properties.lat).toFixed(1)}&deg;N, {Number(hoverInfo.properties.lon).toFixed(1)}&deg;E]</span>
            <span className="text-slate-300 font-bold">{hoverInfo.properties.region_name}</span>
          </div>

          <div className="grid grid-cols-2 gap-x-3 gap-y-1 mt-1.5">
            <div>
              <span className="text-slate-400">NCUM Precip:</span>{" "}
              <strong className="text-slate-100">{hoverInfo.properties.f_precip} mm</strong>
            </div>
            <div>
              <span className="text-slate-400">Bust Prob:</span>{" "}
              <strong className={hoverInfo.properties.bust_prob >= 0.7 ? "text-critical" : "text-amber-400"}>
                {(hoverInfo.properties.bust_prob * 100).toFixed(0)}%
              </strong>
            </div>
            <div>
              <span className="text-slate-400">FCI Score:</span>{" "}
              <strong className={hoverInfo.properties.fci < 40 ? "text-critical" : "text-emerald-400"}>
                {Number(hoverInfo.properties.fci).toFixed(1)}/100
              </strong>
            </div>
            <div>
              <span className="text-slate-400">CQR Bound:</span>{" "}
              <strong className="text-amber-300">{hoverInfo.properties.cqr_bounds}</strong>
            </div>
          </div>
          <div className="text-[9px] text-primary/80 mt-1 italic">Click cell to inspect TreeSHAP physics</div>
        </div>
      )}
    </div>
  );
};
