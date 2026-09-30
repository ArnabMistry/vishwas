"use client";

import React, { useEffect, useState } from "react";
import { Play, Pause, ChevronLeft, ChevronRight, AlertTriangle, Layers } from "lucide-react";

interface TimelineOverlayProps {
  leadTime: number;
  onLeadTimeChange: (newLeadTime: number) => void;
  isLoading: boolean;
}

export const TimelineOverlay: React.FC<TimelineOverlayProps> = ({
  leadTime,
  onLeadTimeChange,
  isLoading,
}) => {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        onLeadTimeChange((leadTime % 10) + 1);
      }, 2200);
    }
    return () => clearInterval(interval);
  }, [isPlaying, leadTime, onLeadTimeChange]);

  const handlePrev = () => {
    if (leadTime > 1) onLeadTimeChange(leadTime - 1);
  };

  const handleNext = () => {
    if (leadTime < 10) onLeadTimeChange(leadTime + 1);
  };

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 w-[94%] max-w-4xl bg-slate-950/90 border border-slate-700/80 backdrop-blur-md rounded-sm p-3.5 shadow-2xl select-none">
      {/* Top row: Controls, Timeline indicators & Lead Time Banner */}
      <div className="flex items-center justify-between gap-4 mb-2.5">
        {/* Playback Controls */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className={`flex items-center gap-1.5 px-3 py-1 text-xs font-mono font-medium rounded-sm border transition-colors ${
              isPlaying
                ? "bg-primary text-slate-950 border-primary font-bold"
                : "bg-slate-900 hover:bg-slate-800 text-slate-200 border-slate-700"
            }`}
            title={isPlaying ? "Pause Timeline Playback" : "Auto-advance forecast lead time"}
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            <span>{isPlaying ? "PAUSE" : isLoading ? "SYNCING..." : "PLAY TIMELINE"}</span>
          </button>

          <button
            onClick={handlePrev}
            disabled={leadTime <= 1}
            className="p-1 rounded-sm bg-slate-900 hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-slate-900 border border-slate-700 text-slate-300"
            title="Previous Day"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <button
            onClick={handleNext}
            disabled={leadTime >= 10}
            className="p-1 rounded-sm bg-slate-900 hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-slate-900 border border-slate-700 text-slate-300"
            title="Next Day"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Center: Lead Time display with D+5 Highlight */}
        <div className="flex items-center gap-2 font-mono text-xs">
          <span className="text-slate-400">FORECAST LEAD:</span>
          <span className="text-sm font-bold text-white px-2 py-0.5 bg-slate-900 border border-slate-700 rounded-sm">
            Day {leadTime} / 10
          </span>
          {leadTime === 5 && (
            <span className="flex items-center gap-1 text-[11px] font-bold text-critical bg-critical/15 px-2 py-0.5 border border-critical/40 rounded-sm animate-pulse">
              <AlertTriangle className="w-3 h-3" />
              DEMO HOTSPOT: ODISHA BUST EPISODE
            </span>
          )}
        </div>

        {/* Right: Bivariate Legend Preview */}
        <div className="hidden sm:flex items-center gap-3 text-[11px] font-mono">
          <span className="text-slate-400 flex items-center gap-1">
            <Layers className="w-3.5 h-3.5 text-primary" />
            CFRF BUST PROB:
          </span>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-[#0F172A] border border-slate-700" title="Stable (<0.3)" />
            <span className="text-slate-400 text-[10px]">0.0</span>
            <div className="w-3 h-3 bg-[#38BDF8]" title="Nominal (0.5)" />
            <div className="w-3 h-3 bg-[#F59E0B]" title="Warning (0.75)" />
            <div className="w-3 h-3 bg-[#E11D48]" title="Severe Bust (>0.85)" />
            <span className="text-slate-400 text-[10px]">1.0</span>
          </div>
        </div>
      </div>

      {/* Scrubbing Range Slider */}
      <div className="relative py-1">
        <input
          type="range"
          min="1"
          max="10"
          step="1"
          value={leadTime}
          onChange={(e) => onLeadTimeChange(parseInt(e.target.value, 10))}
          className="w-full h-2 bg-slate-800 rounded-none appearance-none cursor-pointer border border-slate-700"
        />
      </div>

      {/* Day Tick Badges (D+1 to D+10) */}
      <div className="grid grid-cols-10 gap-1.5 mt-1">
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((day) => {
          const isActive = day === leadTime;
          const isOdishaBustDay = day === 5;
          return (
            <button
              key={day}
              onClick={() => onLeadTimeChange(day)}
              className={`py-1 px-0.5 text-center font-mono text-[11px] rounded-sm transition-all border ${
                isActive
                  ? "bg-primary text-slate-950 border-primary font-bold shadow-md"
                  : isOdishaBustDay
                  ? "bg-critical/20 text-rose-300 border-critical/50 hover:bg-critical/30 font-semibold"
                  : "bg-slate-900/80 text-slate-400 border-slate-800 hover:bg-slate-800 hover:text-slate-200"
              }`}
            >
              <div className="leading-tight">D+{day}</div>
              <div className="text-[9px] opacity-75 font-sans leading-none mt-0.5">
                {isOdishaBustDay ? "CRITICAL" : `${day * 24}h`}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
