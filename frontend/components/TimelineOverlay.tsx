"use client";

import React, { useEffect, useState } from "react";
import { Play, Pause, ChevronLeft, ChevronRight, AlertTriangle, Layers } from "lucide-react";

interface TimelineOverlayProps {
  leadTime: number;
  onLeadTimeChange: (newLeadTime: number) => void;
  isLoading: boolean;
  isInspectorOpen?: boolean;
  isRealMode?: boolean;
}

export const TimelineOverlay: React.FC<TimelineOverlayProps> = ({
  leadTime,
  onLeadTimeChange,
  isLoading,
  isInspectorOpen = false,
  isRealMode: propIsRealMode,
}) => {
  const isRealMode = propIsRealMode !== undefined
    ? propIsRealMode
    : (process.env.NEXT_PUBLIC_DATA_MODE || "").toUpperCase() === "REAL";
  const maxLead = isRealMode ? 9 : 10;
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        onLeadTimeChange((leadTime % maxLead) + 1);
      }, 2200);
    }
    return () => clearInterval(interval);
  }, [isPlaying, leadTime, maxLead, onLeadTimeChange]);

  const handlePrev = () => {
    if (leadTime > 1) onLeadTimeChange(leadTime - 1);
  };

  const handleNext = () => {
    if (leadTime < maxLead) onLeadTimeChange(leadTime + 1);
  };

  const handleDayClick = (day: number) => {
    if (isRealMode && day === 10) return;
    onLeadTimeChange(day);
  };

  return (
    <div
      id="timeline-overlay"
      className={`absolute bottom-2 sm:bottom-3 z-20 bg-slate-950/95 border border-slate-700/80 backdrop-blur-md rounded-sm p-2 shadow-2xl select-none transition-all duration-200 ${
        isInspectorOpen
          ? "left-2 right-2 sm:left-4 sm:right-4 xl:left-[308px] xl:right-[408px] max-w-2xl mx-auto"
          : "left-1/2 -translate-x-1/2 w-[calc(100%-1rem)] sm:w-[calc(100%-1.5rem)] max-w-2xl"
      }`}
    >
      {/* Top row: Controls, Timeline indicators & Lead Time Banner */}
      <div className="flex items-center justify-between gap-2 sm:gap-3 mb-1.5 flex-wrap">
        {/* Playback Controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className={`flex items-center gap-1.5 px-2 sm:px-2.5 py-0.5 text-[10px] sm:text-[11px] font-mono font-medium rounded-sm border transition-colors ${
              isPlaying
                ? "bg-primary text-slate-950 border-primary font-bold"
                : "bg-slate-900 hover:bg-slate-800 text-slate-200 border-slate-700"
            }`}
            title={isPlaying ? "Pause Timeline Playback" : "Auto-advance forecast lead time"}
          >
            {isPlaying ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            <span>{isPlaying ? "PAUSE" : isLoading ? "SYNCING..." : "PLAY"}</span>
          </button>

          <button
            onClick={handlePrev}
            disabled={leadTime <= 1}
            className="p-1 rounded-sm bg-slate-900 hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-slate-900 border border-slate-700 text-slate-300"
            title="Previous Day"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={handleNext}
            disabled={leadTime >= maxLead}
            className="p-1 rounded-sm bg-slate-900 hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-slate-900 border border-slate-700 text-slate-300"
            title="Next Day"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Center: Lead Time display with D+5 Highlight in DEMO */}
        <div className="flex items-center gap-1.5 sm:gap-2 font-mono text-[10px] sm:text-[11px]">
          <span className="text-slate-400">FORECAST LEAD:</span>
          <span className="text-[11px] sm:text-xs font-bold text-white px-1.5 py-0.5 bg-slate-900 border border-slate-700 rounded-sm">
            Day {leadTime} / {maxLead} ({leadTime * 24}h)
          </span>
          {!isRealMode && leadTime === 5 && (
            <span className="flex items-center gap-1 text-[9px] sm:text-[10px] font-bold text-critical bg-critical/15 px-1.5 py-0.5 border border-critical/40 rounded-sm animate-pulse">
              <AlertTriangle className="w-3 h-3" />
              ODISHA BUST
            </span>
          )}
        </div>

        {/* Right: Bivariate Legend Preview */}
        <div className="hidden sm:flex items-center gap-2 text-[10px] font-mono">
          <span className="text-slate-400 flex items-center gap-1">
            <Layers className="w-3 h-3 text-primary" />
            {isRealMode ? "BUST RISK:" : "CFRF BUST:"}
          </span>
          <div className="flex items-center gap-1">
            <div className="w-2.5 h-2.5 bg-[#0F172A] border border-slate-700" title="Stable (<0.3)" />
            <span className="text-slate-500 text-[9px]">0.0</span>
            <div className="w-2.5 h-2.5 bg-[#38BDF8]" title="Nominal (0.5)" />
            <div className="w-2.5 h-2.5 bg-[#F59E0B]" title="Warning (0.75)" />
            <div className="w-2.5 h-2.5 bg-[#E11D48]" title="Severe (>0.85)" />
            <span className="text-slate-500 text-[9px]">1.0</span>
          </div>
        </div>
      </div>

      {/* Scrubbing Range Slider */}
      <div className="relative py-0.5">
        <input
          type="range"
          min="1"
          max={maxLead}
          step="1"
          value={leadTime}
          onChange={(e) => onLeadTimeChange(parseInt(e.target.value, 10))}
          className="w-full h-1.5 bg-slate-800 rounded-none appearance-none cursor-pointer border border-slate-700"
        />
      </div>

      {/* Day Tick Badges (D+1 to D+10) */}
      <div className="grid grid-cols-10 gap-0.5 sm:gap-1 mt-1">
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((day) => {
          const isActive = day === leadTime;
          const isOdishaBustDay = !isRealMode && day === 5;
          const isUnavailable = isRealMode && day === 10;

          if (isUnavailable) {
            return (
              <button
                key={day}
                id={`timeline-day-${day}`}
                disabled
                className="py-0.5 px-0.5 text-center font-mono text-[9px] sm:text-[10px] rounded-sm border opacity-35 cursor-not-allowed bg-slate-950/60 text-slate-600 border-dashed border-slate-800"
                title="D+10 is not empirically available in the current REAL validation dataset."
              >
                <div className="leading-tight text-slate-500">D+10</div>
                <div className="text-[7px] text-slate-600 font-sans leading-none mt-0.5 uppercase tracking-tighter">
                  UNAVAIL
                </div>
              </button>
            );
          }

          return (
            <button
              key={day}
              id={`timeline-day-${day}`}
              onClick={() => handleDayClick(day)}
              className={`py-0.5 px-0.5 text-center font-mono text-[9px] sm:text-[10px] rounded-sm transition-all border ${
                isActive
                  ? "bg-primary text-slate-950 border-primary font-bold shadow-md"
                  : isOdishaBustDay
                  ? "bg-critical/20 text-rose-300 border-critical/50 hover:bg-critical/30 font-semibold"
                  : "bg-slate-900/80 text-slate-400 border-slate-800 hover:bg-slate-800 hover:text-slate-200"
              }`}
            >
              <div className="leading-tight">D+{day}</div>
              <div className="text-[7px] sm:text-[8px] opacity-75 font-sans leading-none mt-0.5">
                {isOdishaBustDay ? "CRITICAL" : `${day * 24}h`}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
