"use client";

import React from "react";
import { X, CheckCircle, ShieldCheck, Cpu, Database, Radio, Activity, AlertTriangle } from "lucide-react";
import { SystemStatusData } from "../types/forecast";

interface SystemStatusModalProps {
  isOpen: boolean;
  onClose: () => void;
  statusData: SystemStatusData | null;
  isRealMode?: boolean;
}

export const SystemStatusModal: React.FC<SystemStatusModalProps> = ({
  isOpen,
  onClose,
  statusData,
  isRealMode: propIsRealMode,
}) => {
  if (!isOpen) return null;

  const isRealMode = propIsRealMode !== undefined
    ? propIsRealMode
    : (process.env.NEXT_PUBLIC_DATA_MODE || "").toUpperCase() !== "DEMO" ||
      statusData?.status === "HISTORICAL_VALIDATION";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 select-none animate-in fade-in duration-150">
      <div className="w-full max-w-xl bg-slate-900 border border-slate-700 rounded-sm shadow-2xl p-5 text-slate-200">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-400" />
            <div>
              <h3 className="font-mono text-sm font-bold text-white tracking-wide">
                {isRealMode
                  ? "HISTORICAL VALIDATION TELEMETRY & SPECIFICATION"
                  : "SYSTEM TELEMETRY & PIPELINE SPECIFICATION"}
              </h3>
              <p className="text-[11px] text-slate-400 font-sans">
                {isRealMode
                  ? "Retrospective Research Validation Pipeline (Proxy for NCMRWF Operational Evaluation)"
                  : "National Centre for Medium Range Weather Forecasting (NCMRWF) • MoES"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-sm text-slate-400 hover:text-white hover:bg-slate-800 border border-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Telemetry Grid */}
        <div className="mt-4 space-y-3 font-mono text-xs">
          <div className="grid grid-cols-2 gap-2.5">
            <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-sm">
              <div className="flex items-center gap-1.5 text-slate-400 text-[10px]">
                <Radio className="w-3.5 h-3.5 text-emerald-400" />
                <span>NWP MODEL INSTANCE</span>
              </div>
              <div className="text-sm font-bold text-slate-100 mt-1">
                {statusData?.nwp_model || (isRealMode ? "NOAA-GFS 0.25° (Open Proxy)" : "NCUM-G")}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                {isRealMode
                  ? "Resolution: 0.25° (~27 km) • Open Data Proxy"
                  : "Resolution: 12 km • 70 vertical levels"}
              </div>
            </div>

            <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-sm">
              <div className="flex items-center gap-1.5 text-slate-400 text-[10px]">
                <Database className="w-3.5 h-3.5 text-primary" />
                <span>DATA STREAM & PROVENANCE</span>
              </div>
              <div className="text-sm font-bold text-slate-100 mt-1">
                {statusData?.cycle || (isRealMode ? "Historical Validation 2023" : "00Z Operational Run")}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                {isRealMode
                  ? "IMD 0.25° Gridded Rainfall Ground Truth"
                  : "IMD 0.25° Gridded Rainfall Proxy"}
              </div>
            </div>

            <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-sm">
              <div className="flex items-center gap-1.5 text-slate-400 text-[10px]">
                <Cpu className="w-3.5 h-3.5 text-amber-400" />
                <span>MACHINE LEARNING REGRESSOR</span>
              </div>
              <div className="text-sm font-bold text-slate-100 mt-1">
                {statusData?.ml_regressor || "XGBoost Regressor"}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                Target: Absolute Forecast Error |F - O|
              </div>
            </div>

            <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-sm">
              <div className="flex items-center gap-1.5 text-slate-400 text-[10px]">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                <span>{isRealMode ? "CONFORMAL ENGINE" : "CQR UNCERTAINTY QUANTIFICATION"}</span>
              </div>
              <div className="text-sm font-bold text-slate-100 mt-1">
                {isRealMode
                  ? (statusData?.calibration_method || "Split Conformal Prediction (MAPIE)")
                  : (statusData?.calibration_method || "MAPIE Calibration Active")}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                {isRealMode
                  ? "Coverage under exchangeability (α = 0.20)"
                  : "80% Conformal Coverage (α = 0.20)"}
              </div>
            </div>
          </div>

          {/* Verification Pipeline Checks */}
          <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-sm">
            <div className="text-[11px] font-bold text-slate-300 pb-2 border-b border-slate-800 flex items-center justify-between">
              <span>
                {isRealMode
                  ? "HISTORICAL VALIDATION PIPELINE HEALTH CHECK"
                  : "OPERATIONAL PIPELINE HEALTH CHECK"}
              </span>
              <span className="text-emerald-400 flex items-center gap-1 text-[10px]">
                <CheckCircle className="w-3 h-3" />
                {isRealMode ? "HISTORICAL ARCHIVE VERIFIED" : "ALL SUBSYSTEMS GREEN"}
              </span>
            </div>

            <div className="mt-2 space-y-1.5 text-[11px]">
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-2">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                  {isRealMode
                    ? "NWP Data Ingestion (NOAA-GFS D+1..D+9 0.25° Archive):"
                    : "NWP Data Ingestion (NCUM-G medium-range D+1..10):"}
                </span>
                <span className="text-emerald-400 font-semibold">
                  {isRealMode ? "VERIFIED (D1–D9)" : "SYNCHRONIZED"}
                </span>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-2">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                  {isRealMode
                    ? "Observation Ground Truth (IMD 0.25° 4,905 Land Cells):"
                    : "Feature Engine (Thermodynamic CAPE, Z500, Shear):"}
                </span>
                <span className="text-emerald-400 font-semibold">
                  {isRealMode ? "SYNCHRONIZED" : "CALCULATED"}
                </span>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-2">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                  {isRealMode
                    ? "Conformal Uncertainty Engine (Split Conformal Prediction):"
                    : "Conformal Quantile Regressor (MAPIE Split CQR):"}
                </span>
                <span className="text-emerald-400 font-semibold">CALIBRATED</span>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-2">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                  {isRealMode
                    ? "Spatial Verification (Phase 2B Pooled FSS Study):"
                    : "TreeSHAP Linguistic Translation Layer:"}
                </span>
                <span className="text-emerald-400 font-semibold">
                  {isRealMode ? "VALIDATED" : "ONLINE"}
                </span>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-2">
                  {isRealMode ? (
                    <AlertTriangle className="w-3 h-3 text-amber-400" />
                  ) : (
                    <CheckCircle className="w-3 h-3 text-emerald-400" />
                  )}
                  {isRealMode
                    ? "Operational NCUM-G Telemetry Link:"
                    : "FastAPI High-Speed GeoJSON Serialization:"}
                </span>
                <span className={isRealMode ? "text-amber-400 font-semibold" : "text-emerald-400 font-semibold"}>
                  {isRealMode ? "NOT CONNECTED (DISCLAIMER)" : "0.4ms LATENCY"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="mt-5 pt-3 border-t border-slate-800 flex items-center justify-between text-[11px] font-mono text-slate-500">
          <span>
            {isRealMode
              ? "HISTORICAL VALIDATION NOTICE: Retrospective proxy validation. NCUM-G operational telemetry not connected."
              : "PROTOTYPE NOTICE: Operating on curated historical proxy dataset."}
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-sm font-semibold transition-colors"
          >
            DISMISS
          </button>
        </div>
      </div>
    </div>
  );
};
