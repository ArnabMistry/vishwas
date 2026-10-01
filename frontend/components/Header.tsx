"use client";

import React, { useEffect, useState } from "react";
import { Activity, Radio, Database, ShieldCheck, AlertCircle, RefreshCw } from "lucide-react";
import { SystemStatusData } from "../types/forecast";

interface HeaderProps {
  leadTime: number;
  isLoading: boolean;
  systemError: string | null;
  onOpenStatusModal: () => void;
  systemStatus: SystemStatusData | null;
  isRealMode?: boolean;
  onToggleMode?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  leadTime,
  isLoading,
  systemError,
  onOpenStatusModal,
  systemStatus,
  isRealMode: propIsRealMode,
  onToggleMode,
}) => {
  const [timeUtc, setTimeUtc] = useState<string>("");
  const [timeIst, setTimeIst] = useState<string>("");

  useEffect(() => {
    const updateClocks = () => {
      const now = new Date();
      setTimeUtc(now.toUTCString().slice(17, 25) + " UTC");
      setTimeIst(
        now.toLocaleTimeString("en-IN", {
          timeZone: "Asia/Kolkata",
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }) + " IST"
      );
    };
    updateClocks();
    const interval = setInterval(updateClocks, 1000);
    return () => clearInterval(interval);
  }, []);

  const isRealMode = propIsRealMode !== undefined
    ? propIsRealMode
    : (process.env.NEXT_PUBLIC_DATA_MODE || "").toUpperCase() !== "DEMO";

  return (
    <header className="w-full bg-slate-950 border-b border-slate-800 text-slate-200 z-30 select-none">
      {/* Top Banner if disconnected */}
      {systemError && (
        <div className="bg-critical/90 text-white px-4 py-1.5 text-xs font-mono font-semibold flex items-center justify-between border-b border-critical">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 animate-pulse shrink-0" />
            <span className="truncate">SYSTEM ERROR: {systemError}</span>
          </div>
          <span className="text-[11px] underline cursor-pointer shrink-0 ml-2" onClick={() => window.location.reload()}>
            RECONNECT
          </span>
        </div>
      )}

      <div className="h-14 px-3 sm:px-4 flex items-center justify-between gap-2">
        {/* Left: Branding & Model Identity */}
        <div className="flex items-center gap-2 sm:gap-4 min-w-0">
          <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
            <div className="w-8 h-8 rounded-sm bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center font-mono font-black text-slate-950 text-base shadow-sm">
              V
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                <span className="font-mono font-bold tracking-wider text-sm sm:text-base text-white">VISHWAS</span>
                <span className="text-[9px] sm:text-[10px] uppercase font-mono px-1 sm:px-1.5 py-0.5 rounded-sm bg-slate-800 border border-slate-700 text-primary font-medium tracking-tight">
                  NCMRWF / MoES
                </span>
                <button
                  id="data-mode-indicator"
                  onClick={onToggleMode}
                  className={`text-[9px] sm:text-[10px] uppercase font-mono px-1.5 py-0.5 rounded-sm border font-medium tracking-tight transition-colors cursor-pointer ${
                    isRealMode
                      ? "bg-emerald-950/80 border-emerald-700/80 text-emerald-400 hover:bg-emerald-900/80"
                      : "bg-slate-800/80 border-slate-700/80 text-slate-400 hover:bg-slate-700/80"
                  }`}
                  title={onToggleMode ? `Click to switch to ${isRealMode ? "SYNTHETIC DEMO" : "REAL DATA"} mode` : undefined}
                >
                  {isRealMode ? "[REAL DATA: GFS 0.25°]" : "[SYNTHETIC DEMO]"}
                </button>
                {isLoading && (
                  <RefreshCw className="w-3.5 h-3.5 text-primary animate-spin" />
                )}
              </div>
              <p className="text-[10px] sm:text-[11px] text-slate-400 font-sans tracking-tight truncate max-w-[200px] sm:max-w-none">
                {isRealMode
                  ? "Forecast Reliability Engine • Split Conformal Prediction"
                  : "Forecast Reliability Engine • Conformalized Quantile Regression (CQR)"}
              </p>
            </div>
          </div>

          <div className="hidden xl:block h-6 w-[1px] bg-slate-800 mx-1" />

          {/* Operational Run Context */}
          <div className="hidden xl:flex items-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-1.5 text-slate-400">
              <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
              <span>
                Model:{" "}
                <strong className="text-slate-200">
                  {isRealMode ? "NOAA-GFS 0.25° (Aug 2023)" : "NCUM-G (12km, 70L)"}
                </strong>
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-400">
              <Database className="w-3.5 h-3.5 text-primary" />
              <span>
                Cycle:{" "}
                <strong className="text-slate-200">
                  {isRealMode ? "Aug 2023 Validation" : "00Z Assimilation"}
                </strong>
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-400">
              <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
              <span>
                Coverage:{" "}
                <strong className="text-slate-200">
                  {isRealMode ? "80% Conformal Bound" : "80% CQR Bound"}
                </strong>
              </span>
            </div>
          </div>
        </div>

        {/* Right: Operational Clocks, Lead Time Badge & Telemetry Button */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <div className="px-2.5 sm:px-3 py-1 bg-slate-900/95 border border-primary/40 shadow-[0_0_12px_rgba(56,189,248,0.15)] rounded-sm font-mono text-xs flex items-center gap-1.5 sm:gap-2">
            <span className="text-slate-400 text-[10px] sm:text-[11px] hidden xs:inline font-semibold">LEAD:</span>
            <span className="text-primary font-black text-xs sm:text-sm">D+{leadTime}</span>
            <span className="text-slate-400 text-[9px] sm:text-[10px] font-semibold">({leadTime * 24}h)</span>
          </div>

          <div className="hidden lg:flex flex-col items-end font-mono text-[10px] sm:text-[11px] leading-tight px-2 py-0.5 bg-slate-900/60 border border-slate-800 rounded-sm">
            <span className="text-slate-300 font-semibold">{timeUtc || "00:00:00 UTC"}</span>
            <span className="text-slate-400">{timeIst || "00:00:00 IST"}</span>
          </div>

          <button
            onClick={onOpenStatusModal}
            className="flex items-center gap-1.5 px-2 sm:px-3 py-1.5 bg-slate-800 hover:bg-slate-700/80 active:bg-slate-800 border border-slate-700 hover:border-slate-600 rounded-sm text-[11px] sm:text-xs font-mono transition-colors"
            title="Inspect System Telemetry & Pipeline Status"
          >
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-slate-200 hidden sm:inline">STATUS:</span>
            <span className="text-emerald-400 font-bold truncate max-w-[90px] sm:max-w-none">
              {isRealMode ? (systemStatus?.status === "HISTORICAL_VALIDATION" ? "VALIDATION" : "OPERATIONAL") : (systemStatus?.status || "OPERATIONAL")}
            </span>
          </button>
        </div>
      </div>
    </header>
  );
};
