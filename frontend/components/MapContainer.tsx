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
  isRealMode?: boolean;
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
  isRealMode: propIsRealMode,
}) => {
  const isRealMode = propIsRealMode !== undefined
    ? propIsRealMode
    : (process.env.NEXT_PUBLIC_DATA_MODE || "").toUpperCase() !== "DEMO";
  const mapRef = useRef<MapRef | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [hoverInfo, setHoverInfo] = useState<{
    x: number;
    y: number;
    properties: GridProperties;
  } | null>(null);
  const [cursor, setCursor] = useState<string>("auto");

  // Collision-aware HUD tooltip positioning
  const getTooltipStyle = useCallback((cursorX: number, cursorY: number): React.CSSProperties => {
    const TOOLTIP_WIDTH = 268;
    const TOOLTIP_HEIGHT = 135;
    const GAP = 12;

    const container = containerRef.current?.getBoundingClientRect();
    const containerW = container ? container.width : (typeof window !== "undefined" ? window.innerWidth : 1000);
    const containerH = container ? container.height : (typeof window !== "undefined" ? window.innerHeight : 800);
    const containerL = container ? container.left : 0;
    const containerT = container ? container.top : 0;

    // Obstacle 1: Historical Overview panel (left side)
    const leftEl = typeof document !== "undefined" ? document.getElementById("operations-panel") : null;
    let safeLeft = GAP;
    if (leftEl) {
      const lr = leftEl.getBoundingClientRect();
      safeLeft = Math.max(safeLeft, lr.right - containerL + GAP);
    }

    // Obstacle 2: Cell Inspector panel (right side)
    const rightEl = typeof document !== "undefined" ? document.getElementById("region-inspector") : null;
    let safeRight = containerW - GAP;
    if (rightEl) {
      const rr = rightEl.getBoundingClientRect();
      safeRight = Math.min(safeRight, rr.left - containerL - GAP);
    }

    // Obstacle 3: Bottom forecast timeline/control bar
    const bottomEl = typeof document !== "undefined" ? document.getElementById("timeline-overlay") : null;
    let safeBottom = containerH - GAP;
    let timelineLeft = 0;
    let timelineRight = containerW;
    if (bottomEl) {
      const br = bottomEl.getBoundingClientRect();
      safeBottom = Math.min(safeBottom, br.top - containerT - GAP);
      timelineLeft = br.left - containerL;
      timelineRight = br.right - containerL;
    }

    // Obstacle 4: Map zoom controls (top-right)
    const zoomEl = containerRef.current?.querySelector(".maplibregl-ctrl-top-right") as HTMLElement | null;
    let zoomLeft = containerW;
    let zoomBottom = 0;
    if (zoomEl) {
      const zr = zoomEl.getBoundingClientRect();
      zoomLeft = zr.left - containerL - GAP;
      zoomBottom = zr.bottom - containerT + GAP;
    }

    // 1. Determine Horizontal Position
    // Prefer below/right of cursor:
    const posXRight = cursorX + 16;
    const collidesRight =
      posXRight + TOOLTIP_WIDTH > safeRight ||
      (cursorY < zoomBottom && posXRight + TOOLTIP_WIDTH > zoomLeft);

    const posXLeft = cursorX - TOOLTIP_WIDTH - 16;
    const collidesLeft = posXLeft < safeLeft;

    let posX = posXRight;
    if (collidesRight && !collidesLeft) {
      // Flip to left side of cursor
      posX = posXLeft;
    } else if (collidesRight && collidesLeft) {
      // Free corridor is tight: clamp within safe corridor
      posX = Math.max(safeLeft, Math.min(safeRight - TOOLTIP_WIDTH, posXRight));
    } else if (posXRight < safeLeft) {
      // Cursor is near or overlapping left panel: flip/shift to right of left panel
      posX = safeLeft;
    }

    // Final horizontal clamp to safe corridor
    const maxAvailableX = Math.max(safeLeft, safeRight - TOOLTIP_WIDTH);
    if (posX > maxAvailableX) posX = maxAvailableX;
    if (posX < safeLeft) posX = safeLeft;

    // 2. Determine Vertical Position
    // Prefer below cursor:
    let posY = cursorY + 16;

    // Check collision with timeline if tooltip is in horizontal timeline span
    const inTimelineX = posX + TOOLTIP_WIDTH > timelineLeft && posX < timelineRight;
    const effectiveBottom = inTimelineX ? safeBottom : containerH - GAP;

    if (posY + TOOLTIP_HEIGHT > effectiveBottom) {
      // Flip to above cursor
      posY = cursorY - TOOLTIP_HEIGHT - 16;
    }

    // Clamp vertically
    const safeTop = GAP;
    if (posY < safeTop) {
      posY = safeTop;
    }
    if (posY + TOOLTIP_HEIGHT > effectiveBottom) {
      posY = Math.max(safeTop, effectiveBottom - TOOLTIP_HEIGHT);
    }

    return {
      left: `${Math.round(posX)}px`,
      top: `${Math.round(posY)}px`,
    };
  }, []);

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

  // Hover handler specifically bound to forecast grid cell features
  const handleMouseMove = useCallback(
    (event: { features?: Array<{ properties?: Record<string, unknown>; layer?: { id?: string } }>; point: { x: number; y: number } }) => {
      const { features, point } = event;
      // Strictly verify that the feature belongs to the forecast grid layer and has a valid grid_id
      const hoveredFeature = features && features.find(
        (f) => f.layer?.id === "bust-layer" && Boolean((f.properties as unknown as GridProperties)?.grid_id)
      );

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

  // Dismiss hover tooltip immediately if cursor enters fixed UI overlays or leaves window
  useEffect(() => {
    const handleGlobalPointerMove = (e: PointerEvent) => {
      const target = e.target as Element | null;
      if (
        target &&
        target.closest(
          "#operations-panel, #region-inspector, #timeline-overlay, .maplibregl-ctrl, .maplibregl-ctrl-group"
        )
      ) {
        setHoverInfo(null);
        setCursor("auto");
      }
    };

    const handleWindowBlur = () => {
      setHoverInfo(null);
      setCursor("auto");
    };

    window.addEventListener("pointermove", handleGlobalPointerMove, { passive: true });
    window.addEventListener("blur", handleWindowBlur);
    document.addEventListener("mouseleave", handleWindowBlur);

    return () => {
      window.removeEventListener("pointermove", handleGlobalPointerMove);
      window.removeEventListener("blur", handleWindowBlur);
      document.removeEventListener("mouseleave", handleWindowBlur);
    };
  }, []);

  // MapLibre layer-specific event bindings for 'bust-layer'
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;

    const layerId = "bust-layer";

    const onGridMouseMove = (e: maplibregl.MapLayerMouseEvent) => {
      const feature = e.features && e.features[0];
      if (feature && feature.properties) {
        const props = feature.properties as unknown as GridProperties;
        if (props.grid_id) {
          setCursor("pointer");
          setHoverInfo({
            x: e.point.x,
            y: e.point.y,
            properties: props,
          });
          return;
        }
      }
      setCursor("auto");
      setHoverInfo(null);
    };

    const onGridMouseLeave = () => {
      setCursor("auto");
      setHoverInfo(null);
    };

    const onMapMouseMove = (e: maplibregl.MapMouseEvent) => {
      try {
        const features = map.queryRenderedFeatures(e.point, { layers: [layerId] });
        if (!features || features.length === 0) {
          setCursor("auto");
          setHoverInfo(null);
        }
      } catch {
        // layer might not be initialized yet
      }
    };

    const attachListeners = () => {
      if (map.getLayer(layerId)) {
        map.off("mousemove", layerId, onGridMouseMove);
        map.off("mouseleave", layerId, onGridMouseLeave);
        map.off("mousemove", onMapMouseMove);
        map.off("mouseout", onGridMouseLeave);

        map.on("mousemove", layerId, onGridMouseMove);
        map.on("mouseleave", layerId, onGridMouseLeave);
        map.on("mousemove", onMapMouseMove);
        map.on("mouseout", onGridMouseLeave);
      }
    };

    attachListeners();
    map.on("styledata", attachListeners);

    return () => {
      try {
        map.off("mousemove", layerId, onGridMouseMove);
        map.off("mouseleave", layerId, onGridMouseLeave);
        map.off("mousemove", onMapMouseMove);
        map.off("mouseout", onGridMouseLeave);
        map.off("styledata", attachListeners);
      } catch {
        // map cleanup
      }
    };
  }, [gridData]);

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

  // Highlight fill layer for the selected cell
  const highlightFillLayerStyle: LayerProps = useMemo(
    () => ({
      id: "bust-highlight-fill",
      type: "fill",
      source: "forecast-grid",
      paint: {
        "fill-color": "#38BDF8",
        "fill-opacity": 0.28,
      },
      filter: selectedGridId ? ["==", ["get", "grid_id"], selectedGridId] : ["==", ["get", "grid_id"], ""],
    }),
    [selectedGridId]
  );

  // High-contrast highlight border for the selected cell
  const highlightLayerStyle: LayerProps = useMemo(
    () => ({
      id: "bust-highlight",
      type: "line",
      source: "forecast-grid",
      paint: {
        "line-color": "#FFFFFF",
        "line-width": 3.0,
        "line-opacity": 1.0,
      },
      filter: selectedGridId ? ["==", ["get", "grid_id"], selectedGridId] : ["==", ["get", "grid_id"], ""],
    }),
    [selectedGridId]
  );

  return (
    <div ref={containerRef} className="relative w-full h-full bg-[#080D1A] overflow-hidden">
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
            <Layer {...highlightFillLayerStyle} />
            <Layer {...highlightLayerStyle} />
          </Source>
        )}
      </Map>

      {/* Lightweight HUD Tooltip on Hover with Collision-Aware Boundary Positioning */}
      {hoverInfo && (
        <div
          className="pointer-events-none absolute z-40 bg-slate-950/95 border border-slate-700/90 rounded-sm p-2 shadow-2xl backdrop-blur-md text-[11px] font-mono text-slate-200 w-[268px]"
          style={getTooltipStyle(hoverInfo.x, hoverInfo.y)}
        >
          <div className="flex items-center justify-between gap-3 text-slate-400 pb-1 border-b border-slate-800 text-[10px]">
            <span>[{Number(hoverInfo.properties.lat).toFixed(1)}&deg;N, {Number(hoverInfo.properties.lon).toFixed(1)}&deg;E]</span>
            <span className="text-slate-300 font-bold">{hoverInfo.properties.region_name}</span>
          </div>

          <div className="grid grid-cols-2 gap-x-3 gap-y-1 mt-1.5">
            <div>
              <span className="text-slate-400">{isRealMode ? "GFS Precip:" : "NCUM Precip:"}</span>{" "}
              <strong className="text-slate-100">{hoverInfo.properties.f_precip} mm</strong>
            </div>
            <div>
              <span className="text-slate-400">{isRealMode ? "Bust Risk:" : "Bust Prob:"}</span>{" "}
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
              <span className="text-slate-400">{isRealMode ? "Conformal Bound:" : "CQR Bound:"}</span>{" "}
              <strong className="text-amber-300">{hoverInfo.properties.cqr_bounds}</strong>
            </div>
          </div>
          <div className="text-[9px] text-primary/80 mt-1 italic">Click cell to inspect TreeSHAP physics</div>
        </div>
      )}
    </div>
  );
};
