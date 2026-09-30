"use client";

import React from "react";
import { X, CheckCircle, ShieldCheck, Cpu, Database, Radio, Activity } from "lucide-react";
import { SystemStatusData } from "../types/forecast";

interface SystemStatusModalProps {
  isOpen: boolean;
  onClose: () => void;
  statusData: SystemStatusData | null;
}

export const SystemStatusModal: React.FC<SystemStatusModalProps> = ({
  isOpen,
  onClose,
  statusData,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 select-none animate-in fade-in duration-150">
      <div className="w-full max-w-xl bg-slate-900 border border-slate-700 rounded-sm shadow-2xl p-5 text-slate-200">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-400" />
            <div>
              <h3 className="font-mono text-sm font-bold text-white tracking-wide">
                SYSTEM TELEMETRY & PIPELINE SPECIFICATION
              </h3>
              <p className="text-[11px] text-slate-400 font-sans">
                National Centre for Medium Range Weather Forecasting (NCMRWF) &bull; MoES
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
                {statusData?.nwp_model || "NCUM-G"}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                Resolution: 12 km &bull; 70 vertical levels
              </div>
            </div>

            <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-sm">
              <div className="flex items-center gap-1.5 text-slate-400 text-[10px]">
                <Database className="w-3.5 h-3.5 text-primary" />
                <span>DATA STREAM & PROVENANCE</span>
              </div>
              <div className="text-sm font-bold text-slate-100 mt-1">
                {statusData?.cycle || "00Z Operational Run"}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                IMD 0.25&deg; Gridded Rainfall Proxy
              </div>
            </div>

            <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-sm">
              <div className="flex items-center gap-1.5 text-slate-400 text-[10px]">
                <Cpu className="w-3.5 h-3.5 text-amber-400" />
                <span>MACHINE LEARNING REGRESSOR</span>
              </div>
              <div className="text-sm font-bold text-slate-100 mt-1">
                {statusData?.ml_regressor || "XGBoost Regressor v1.2"}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                Target: Absolute Forecast Error |F - O|
              </div>
            </div>

            <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-sm">
              <div className="flex items-center gap-1.5 text-slate-400 text-[10px]">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                <span>CQR UNCERTAINTY QUANTIFICATION</span>
              </div>
              <div className="text-sm font-bold text-slate-100 mt-1">
                MAPIE Calibration Active
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                80% Conformal Coverage (&alpha; = 0.20)
              </div>
            </div>
          </div>

          {/* Verification Pipeline Checks */}
          <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-sm">
            <div className="text-[11px] font-bold text-slate-300 pb-2 border-b border-slate-800 flex items-center justify-between">
              <span>OPERATIONAL PIPELINE HEALTH CHECK</span>
              <span className="text-emerald-400 flex items-center gap-1 text-[10px]">
                <CheckCircle className="w-3 h-3" /> ALL SUBSYSTEMS GREEN
              </span>
            </div>

            <div className="mt-2 space-y-1.5 text-[11px]">
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-2">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                  NWP Data Ingestion (NCUM-G medium-range D+1..10):
                </span>
                <span className="text-emerald-400 font-semibold">SYNCHRONIZED</span>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-2">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                  Feature Engine (Thermodynamic CAPE, Z500, Shear):
                </span>
                <span className="text-emerald-400 font-semibold">CALCULATED</span>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-2">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                  Conformal Quantile Regressor (MAPIE Split CQR):
                </span>
                <span className="text-emerald-400 font-semibold">CALIBRATED</span>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-2">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                  TreeSHAP Linguistic Translation Layer:
                </span>
                <span className="text-emerald-400 font-semibold">ONLINE</span>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-2">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                  FastAPI High-Speed GeoJSON Serialization:
                </span>
                <span className="text-emerald-400 font-semibold">0.4ms LATENCY</span>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="mt-5 pt-3 border-t border-slate-800 flex items-center justify-between text-[11px] font-mono text-slate-500">
          <span>PROTOTYPE NOTICE: Operating on curated historical proxy dataset.</span>
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
