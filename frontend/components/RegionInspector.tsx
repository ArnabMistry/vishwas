"use client";

import React, { useState } from "react";
import {
  X,
  AlertTriangle,
  Compass,
  TrendingDown,
  ShieldAlert,
  Gauge
} from "lucide-react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, CartesianGrid } from "recharts";
import { GridProperties, PointDetailsResponse } from "../types/forecast";

interface RegionInspectorProps {
  properties: GridProperties | null;
  pointDetails: PointDetailsResponse | null;
  onClose: () => void;
  leadTime: number;
}

export const RegionInspector: React.FC<RegionInspectorProps> = ({
  properties,
  pointDetails,
  onClose,
  leadTime,
}) => {
  const [viewMode, setViewMode] = useState<"fss" | "analogs">("fss");

  if (!properties) return null;

  const fci = properties.fci;
  const bustProb = properties.bust_prob;
  const isHighRisk = bustProb >= 0.70;
  const isSevereBust = bustProb >= 0.85;

  // FCI status tier
  const getFciTier = (score: number) => {
    if (score >= 70) return { label: "NOMINAL RELIABILITY", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30" };
    if (score >= 40) return { label: "MODERATE FRAGILITY", color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/30" };
    return { label: "SEVERE FORECAST BUST", color: "text-rose-400", bg: "bg-rose-500/10 border-rose-500/30" };
  };

  const fciTier = getFciTier(fci);

  // FSS data: fallback from properties or pointDetails
  const fssData = pointDetails?.fss_decay || properties.fss_decay || [
    { day: "D+1", fss: 0.92, threshold: 0.5 },
    { day: "D+2", fss: 0.84, threshold: 0.5 },
    { day: "D+3", fss: 0.71, threshold: 0.5 },
    { day: "D+4", fss: 0.46, threshold: 0.5 },
    { day: "D+5", fss: 0.32, threshold: 0.5 },
    { day: "D+6", fss: 0.25, threshold: 0.5 },
    { day: "D+7", fss: 0.20, threshold: 0.5 },
    { day: "D+8", fss: 0.18, threshold: 0.5 },
    { day: "D+9", fss: 0.15, threshold: 0.5 },
    { day: "D+10", fss: 0.12, threshold: 0.5 },
  ];

  const analogs = pointDetails?.analogs || [
    {
      event_name: "2020 Bay of Bengal Monsoon Low",
      date: "August 18, 2020",
      synoptic_similarity: 94.2,
      observed_error: "+52.4 mm (Dry NWP bias)",
      outcome: "Severe inland underestimation; heavy waterlogging over coastal belt.",
    },
    {
      event_name: "2019 Cyclone Fani Outer Rainband",
      date: "May 2, 2019",
      synoptic_similarity: 88.7,
      observed_error: "+38.6 mm (Track offset)",
      outcome: "Convective core displaced 65 km eastward in D+4 forecast.",
    },
  ];

  return (
    <aside className="absolute top-14 right-0 bottom-0 w-[420px] max-w-[90vw] bg-slate-900/95 border-l border-slate-700/80 backdrop-blur-md p-4 flex flex-col z-20 shadow-2xl overflow-y-auto select-none">
      {/* Header with Title & Coordinates */}
      <div className="flex items-start justify-between pb-3 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-1.5 text-xs font-mono text-slate-400">
            <Compass className="w-3.5 h-3.5 text-primary" />
            <span>GRID [{properties.lat.toFixed(1)}°N, {properties.lon.toFixed(1)}°E]</span>
            <span className="text-slate-600">&bull;</span>
            <span className="text-slate-300">D+{leadTime}</span>
          </div>
          <h2 className="text-base font-bold text-white tracking-tight mt-0.5">
            {properties.region_name}
          </h2>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-sm text-slate-400 hover:text-white hover:bg-slate-800 border border-slate-800 transition-colors"
          title="Close Inspector"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="mt-4 space-y-4 font-sans text-xs">
        {/* Core Metric Banner: FCI & CQR Bounds */}
        <div className={`p-3.5 rounded-sm border ${fciTier.bg}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Gauge className={`w-4 h-4 ${fciTier.color}`} />
              <span className="font-mono font-bold text-[11px] tracking-wide text-slate-300">
                FORECAST CONFIDENCE INDICATOR
              </span>
            </div>
            <span className={`font-mono text-[10px] font-bold px-1.5 py-0.5 rounded-sm uppercase ${fciTier.color} bg-slate-950/60 border border-current`}>
              {fciTier.label}
            </span>
          </div>

          <div className="flex items-baseline gap-2 mt-2">
            <span className={`font-mono text-3xl font-black ${fciTier.color}`}>
              {fci.toFixed(1)}
            </span>
            <span className="font-mono text-slate-400 text-xs">/ 100</span>
            <span className="ml-auto font-mono text-xs text-slate-300">
              Bust Prob: <strong className={isHighRisk ? "text-critical" : "text-slate-200"}>{(bustProb * 100).toFixed(0)}%</strong>
            </span>
          </div>

          {/* Conformal CQR Bounds */}
          <div className="mt-3 pt-2.5 border-t border-slate-700/40 font-mono text-[11px]">
            <div className="text-slate-400 flex items-center justify-between">
              <span>80% CONFORMAL ERROR BOUND (CQR):</span>
              <span className="text-amber-300 font-bold">{properties.cqr_bounds}</span>
            </div>
            <div className="mt-1 text-[10px] text-slate-400 leading-tight">
              Mathematically guaranteed marginal coverage: deterministic NCUM rainfall ({properties.f_precip} mm) is expected to diverge by +{properties.cqr_lower}mm to +{properties.cqr_upper}mm.
            </div>
          </div>
        </div>

        {/* Deterministic Forecast vs Conformal Expectation */}
        <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
          <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-sm">
            <div className="text-slate-400 text-[10px]">NCUM RAW PRECIP</div>
            <div className="text-sm font-bold text-slate-200 mt-0.5">{properties.f_precip} mm/day</div>
            <div className="text-[9px] text-slate-400 mt-0.5">Model output</div>
          </div>
          <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-sm">
            <div className="text-slate-400 text-[10px]">ENSEMBLE SPREAD (&sigma;)</div>
            <div className="text-sm font-bold text-primary mt-0.5">&plusmn;{properties.ensemble_spread} mm</div>
            <div className="text-[9px] text-slate-400 mt-0.5">NEPS-G variance</div>
          </div>
        </div>

        {/* Linguistic TreeSHAP Driver Matrix */}
        <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-sm">
          <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-slate-300 pb-2 border-b border-slate-800/80">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            <span>PHYSICAL BUST ATTRIBUTION (TreeSHAP)</span>
          </div>

          <div className="mt-2.5 space-y-2">
            {properties.shap_drivers && properties.shap_drivers.map((driver, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 p-2 bg-slate-900 border border-slate-800 rounded-sm"
              >
                <AlertTriangle className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${isSevereBust ? "text-critical" : "text-amber-400"}`} />
                <div className="leading-snug text-slate-200 font-sans text-[11px]">
                  <strong className="text-slate-400 font-mono text-[10px] block mb-0.5">
                    DRIVER #{idx + 1}
                  </strong>
                  {driver}
                </div>
              </div>
            ))}
          </div>

          {/* Physical feature diagnostics */}
          <div className="mt-3 pt-2.5 border-t border-slate-800/80 grid grid-cols-2 gap-2 text-[10px] font-mono">
            <div className="flex justify-between text-slate-400">
              <span>CAPE Sounding:</span>
              <span className="text-slate-200 font-semibold">{properties.cape} J/kg</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>|&nabla;Z500| Trough:</span>
              <span className="text-slate-200 font-semibold">{properties.z500_gradient} m/100km</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Deep Wind Shear:</span>
              <span className="text-slate-200 font-semibold">{properties.wind_shear} kts</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Predictability Horizon:</span>
              <span className="text-amber-400 font-bold">D+{properties.fss_horizon_day}</span>
            </div>
          </div>
        </div>

        {/* Verification Visualization: FSS Decay Curve vs Historical Analogs */}
        <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-sm">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
            <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-slate-300">
              <TrendingDown className="w-3.5 h-3.5 text-primary" />
              <span>SPATIAL VERIFICATION</span>
            </div>

            <div className="flex items-center gap-1 font-mono text-[10px]">
              <button
                onClick={() => setViewMode("fss")}
                className={`px-2 py-0.5 rounded-sm border ${
                  viewMode === "fss"
                    ? "bg-primary/20 text-primary border-primary/50 font-bold"
                    : "text-slate-400 border-slate-800 hover:text-slate-200"
                }`}
              >
                FSS DECAY
              </button>
              <button
                onClick={() => setViewMode("analogs")}
                className={`px-2 py-0.5 rounded-sm border ${
                  viewMode === "analogs"
                    ? "bg-primary/20 text-primary border-primary/50 font-bold"
                    : "text-slate-400 border-slate-800 hover:text-slate-200"
                }`}
              >
                ANALOGS
              </button>
            </div>
          </div>

          {viewMode === "fss" ? (
            <div className="mt-2">
              <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mb-1">
                <span>Fractions Skill Score (FSS &ge; 0.5)</span>
                <span className="text-rose-400">--- Limit: 0.5</span>
              </div>
              <div className="h-40 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={fssData} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="day" stroke="#64748b" tick={{ fontSize: 10, fill: "#94a3b8" }} />
                    <YAxis domain={[0, 1]} stroke="#64748b" tick={{ fontSize: 10, fill: "#94a3b8" }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", fontSize: "11px", color: "#e2e8f0" }}
                      formatter={(val) => [String(val), "FSS Skill"]}
                    />
                    <ReferenceLine y={0.5} stroke="#e11d48" strokeDasharray="4 4" label={{ value: "Skill Limit", fill: "#f43f5e", fontSize: 9, position: "insideBottomRight" }} />
                    <Line
                      type="monotone"
                      dataKey="fss"
                      stroke="#38bdf8"
                      strokeWidth={2}
                      dot={{ r: 3, fill: "#38bdf8" }}
                      activeDot={{ r: 5, fill: "#f59e0b" }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-1 text-[10px] text-slate-400 font-sans leading-tight">
                Predictability drops below 0.5 at <strong className="text-rose-400 font-mono">Day {properties.fss_horizon_day}</strong>. Forecaster confidence should rely on ensemble clustering rather than deterministic guidance beyond this lead time.
              </div>
            </div>
          ) : (
            <div className="mt-2 space-y-2">
              {analogs.map((an, i) => (
                <div key={i} className="p-2 bg-slate-900 border border-slate-800 rounded-sm font-sans text-[11px]">
                  <div className="flex items-center justify-between font-mono">
                    <span className="font-bold text-slate-200">{an.event_name}</span>
                    <span className="text-primary text-[10px] bg-primary/10 px-1.5 py-0.5 rounded-sm border border-primary/20">
                      {an.synoptic_similarity}% Match
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5 font-mono">{an.date} &bull; Observed: {an.observed_error}</div>
                  <div className="text-slate-300 mt-1 text-[11px] leading-tight">{an.outcome}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Operational Warning Directive */}
        {isHighRisk && (
          <div className="p-3 bg-critical/10 border border-critical/40 rounded-sm font-sans text-xs">
            <div className="flex items-center gap-1.5 font-mono font-bold text-critical text-[11px]">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>OPERATIONAL DIRECTIVE FOR MOES FORECASTERS</span>
            </div>
            <p className="mt-1.5 text-slate-200 text-[11px] leading-relaxed">
              Deterministic NCUM-G is under-resolving coastal convective intensification. Recommend applying scenario-based probabilistic early warnings for <strong>{properties.region_name}</strong> and flagging flash-flood risk for local disaster management authorities.
            </p>
          </div>
        )}
      </div>
    </aside>
  );
};
