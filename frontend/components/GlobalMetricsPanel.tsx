"use client";

import React, { useState } from "react";
import {
  ChevronUp,
  Activity,
  BarChart2,
  ShieldAlert,
  Flame,
} from "lucide-react";
import { AlertZoneItem, SystemStatusData } from "../types/forecast";

interface GlobalMetricsPanelProps {
  alerts: AlertZoneItem[];
  systemStatus: SystemStatusData | null;
  onSelectAlert: (alert: AlertZoneItem) => void;
  selectedAlertId: string | null;
  currentLeadTime: number;
}

export const GlobalMetricsPanel: React.FC<GlobalMetricsPanelProps> = ({
  alerts,
  systemStatus,
  onSelectAlert,
  selectedAlertId,
  currentLeadTime,
}) => {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);

  // Helper to color DNA barcode vertical ticks (Days 1 to 10)
  const getBarcodeColor = (prob: number) => {
    if (prob >= 0.85) return "bg-[#E11D48]"; // Severe bust (Rose)
    if (prob >= 0.65) return "bg-[#F59E0B]"; // High warning (Amber)
    if (prob >= 0.40) return "bg-[#38BDF8]"; // Nominal (Sky blue)
    return "bg-[#1E3A5F]"; // Low probability (Deep slate)
  };

  return (
    <aside
      className={`absolute top-16 left-3 z-20 transition-all duration-200 select-none ${
        isCollapsed ? "w-11 h-11" : "w-72 max-h-[calc(100vh-5rem)] flex flex-col"
      }`}
    >
      {/* Collapsed toggle button */}
      {isCollapsed ? (
        <button
          onClick={() => setIsCollapsed(false)}
          className="w-11 h-11 bg-slate-900/95 border border-slate-700/80 rounded-sm text-slate-300 hover:text-white flex items-center justify-center shadow-xl backdrop-blur-md"
          title="Expand Operations Overview"
        >
          <BarChart2 className="w-5 h-5 text-primary" />
        </button>
      ) : (
        <div className="bg-slate-900/95 border border-slate-700/80 rounded-sm shadow-2xl backdrop-blur-md p-3 flex flex-col max-h-[calc(100vh-5rem)] overflow-hidden">
          {/* Panel Header */}
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-slate-200">
              <Activity className="w-4 h-4 text-primary" />
              <span>OPERATIONS OVERVIEW</span>
            </div>
            <button
              onClick={() => setIsCollapsed(true)}
              className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-sm transition-colors"
              title="Collapse Panel"
            >
              <ChevronUp className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2.5 mt-2.5 pr-1 text-xs">
            {/* Top Metrics: Network Confidence & High-Risk Count */}
            <div className="grid grid-cols-2 gap-2 font-mono">
              <div className="p-2 bg-slate-950/70 border border-slate-800 rounded-sm">
                <div className="text-[10px] text-slate-400">MEAN NETWORK FCI</div>
                <div className="text-lg font-black text-slate-100 mt-0.5">
                  {systemStatus?.mean_network_fci ? systemStatus.mean_network_fci.toFixed(1) : "67.3"}
                  <span className="text-[11px] font-normal text-slate-500">/100</span>
                </div>
                <div className="text-[9px] text-emerald-400 mt-0.5 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  Baseline Stable
                </div>
              </div>

              <div className="p-2 bg-slate-950/70 border border-slate-800 rounded-sm">
                <div className="text-[10px] text-slate-400">BUST HOTSPOTS</div>
                <div className="text-lg font-black text-critical mt-0.5">
                  {alerts.length}
                </div>
                <div className="text-[9px] text-rose-400 mt-0.5 flex items-center gap-1">
                  <Flame className="w-2.5 h-2.5" />
                  Active In Basin
                </div>
              </div>
            </div>

            {/* Error Distribution Histogram */}
            <div className="p-2 bg-slate-950/70 border border-slate-800 rounded-sm">
              <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mb-1.5">
                <span>GRID ERROR DISTRIBUTION</span>
                <span>840 CELLS</span>
              </div>
              <div className="space-y-1 font-mono text-[10px]">
                <div className="flex items-center gap-2">
                  <span className="w-14 text-slate-400">&gt;85% Bust:</span>
                  <div className="flex-1 bg-slate-800 h-2 rounded-none overflow-hidden">
                    <div className="bg-critical h-full" style={{ width: currentLeadTime >= 4 ? "18%" : "6%" }} />
                  </div>
                  <span className="text-rose-400 font-bold w-7 text-right">
                    {currentLeadTime >= 4 ? "18%" : "6%"}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-14 text-slate-400">60-85%:</span>
                  <div className="flex-1 bg-slate-800 h-2 rounded-none overflow-hidden">
                    <div className="bg-amber-400 h-full" style={{ width: currentLeadTime >= 4 ? "24%" : "14%" }} />
                  </div>
                  <span className="text-amber-400 font-bold w-7 text-right">
                    {currentLeadTime >= 4 ? "24%" : "14%"}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-14 text-slate-400">30-60%:</span>
                  <div className="flex-1 bg-slate-800 h-2 rounded-none overflow-hidden">
                    <div className="bg-primary h-full" style={{ width: "32%" }} />
                  </div>
                  <span className="text-primary font-bold w-7 text-right">32%</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-14 text-slate-400">&lt;30% Safe:</span>
                  <div className="flex-1 bg-slate-800 h-2 rounded-none overflow-hidden">
                    <div className="bg-slate-500 h-full" style={{ width: currentLeadTime >= 4 ? "26%" : "48%" }} />
                  </div>
                  <span className="text-slate-400 font-bold w-7 text-right">
                    {currentLeadTime >= 4 ? "26%" : "48%"}
                  </span>
                </div>
              </div>
            </div>

            {/* Critical Alert Feed with Confidence DNA Barcode */}
            <div>
              <div className="flex items-center justify-between pb-1 text-xs font-mono font-bold text-slate-300">
                <span className="flex items-center gap-1.5">
                  <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                  MONITORED BUST ZONES
                </span>
                <span className="text-[9px] text-slate-500 font-normal">CLICK TO FLY</span>
              </div>

              {/* Dedicated Scroll Container for Alert Zones */}
              <div className="space-y-1.5 mt-1 max-h-48 overflow-y-auto pr-0.5">
                {alerts.map((alert) => {
                  const isSelected = selectedAlertId === alert.id;
                  const isSevere = alert.bust_prob >= 0.85;

                  return (
                    <div
                      key={alert.id}
                      onClick={() => onSelectAlert(alert)}
                      className={`p-2 rounded-sm border cursor-pointer transition-all ${
                        isSelected
                          ? "bg-slate-800/90 border-primary shadow-lg ring-1 ring-primary/40"
                          : "bg-slate-950/70 border-slate-800 hover:border-slate-700 hover:bg-slate-900/80"
                      }`}
                    >
                      <div className="flex items-start justify-between font-mono">
                        <div className="font-bold text-[11px] text-slate-100 flex items-center gap-1">
                          <span className={`w-1.5 h-1.5 rounded-full ${isSevere ? "bg-critical animate-ping" : "bg-amber-400"}`} />
                          {alert.region_name}
                        </div>
                        <span className={`text-[10px] font-bold px-1 rounded-sm ${
                          isSevere ? "bg-critical/20 text-rose-300 border border-critical/40" : "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                        }`}>
                          {(alert.bust_prob * 100).toFixed(0)}%
                        </span>
                      </div>

                      <div className="text-[10px] text-slate-400 font-mono mt-0.5 flex items-center justify-between">
                        <span>Horizon: <strong className="text-slate-200">{alert.lead_time_str}</strong></span>
                        <span className="text-amber-300 font-semibold">{alert.cqr_bounds}</span>
                      </div>

                      {/* Signature Tufte-style Confidence DNA Barcode (Days 1 to 10) */}
                      <div className="mt-1.5 pt-1 border-t border-slate-800/60">
                        <div className="flex items-center justify-between text-[8px] font-mono text-slate-500 mb-0.5">
                          <span>CONFIDENCE DNA:</span>
                          <span>D1 &rarr; D10</span>
                        </div>
                        <div className="grid grid-cols-10 gap-0.5 h-2.5">
                          {alert.dna_barcode.map((prob, idx) => (
                            <div
                              key={idx}
                              className={`h-full ${getBarcodeColor(prob)} ${
                                idx + 1 === currentLeadTime ? "ring-1 ring-white" : ""
                              }`}
                              title={`D+${idx + 1}: ${(prob * 100).toFixed(0)}% bust risk`}
                            />
                          ))}
                        </div>
                      </div>

                      <div className="mt-1 text-[10px] text-slate-400 font-sans truncate">
                        &bull; {alert.primary_driver}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};
