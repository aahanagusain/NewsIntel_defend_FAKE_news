import React from 'react';

/**
 * IndiaPoliticalMapBg:
 * Uses the exact India political map image as a rich cartographic background,
 * sized and positioned to frame the UI cleanly with non-interactive overlay.
 */
export const IndiaPoliticalMapBg: React.FC = () => {
  return (
    <div
      className="fixed inset-0 pointer-events-none z-0 overflow-hidden select-none flex items-center justify-center bg-slate-950"
      style={{ pointerEvents: 'none' }}
    >
      {/* Background ambient tri-color radiance to blend with the neon image aesthetics */}
      <div
        className="absolute top-0 left-0 w-[600px] h-[450px] opacity-25 blur-[160px]"
        style={{ background: 'radial-gradient(circle, #ff9933 0%, transparent 70%)' }}
      />
      <div
        className="absolute bottom-0 right-0 w-[650px] h-[500px] opacity-20 blur-[170px]"
        style={{ background: 'radial-gradient(circle, #0284c7 0%, transparent 70%)' }}
      />

      {/* Exact India Political Map image, resized and centered with high-tech blend */}
      <div className="relative w-full h-full flex items-center justify-center p-4 md:p-8">
        <img
          src="/india-political-map.jpg"
          alt="India Political Map"
          className="max-h-[92vh] max-w-[92vw] w-auto h-auto object-contain rounded-2xl shadow-2xl opacity-60 mix-blend-screen contrast-125 brightness-110 filter drop-shadow-[0_0_35px_rgba(56,189,248,0.25)] transition-all duration-700"
        />

        {/* Subtle vignette mask around edges so cards and text remain readable */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'radial-gradient(ellipse at center, transparent 40%, rgba(2, 6, 23, 0.55) 75%, rgba(2, 6, 23, 0.92) 100%)'
          }}
        />
      </div>

      {/* Cartographic Badge */}
      <div className="absolute bottom-4 left-6 pointer-events-none flex items-center gap-2 text-[11px] font-mono text-cyan-300/80 bg-slate-900/75 backdrop-blur-md px-3.5 py-1.5 rounded-lg border border-cyan-500/30 shadow-lg">
        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
        <span>INDIA POLITICAL MAP • STATES & UNION TERRITORIES</span>
      </div>
    </div>
  );
};
