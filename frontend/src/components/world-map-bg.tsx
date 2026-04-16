/**
 * Decorative SVG world map at low opacity for homepage hero.
 * aria-hidden per accessibility baseline (UI_UX_BRIEF §9).
 */
export function WorldMapBg() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true" data-testid="world-map-bg">
      <svg viewBox="0 0 1200 600" className="w-full h-full opacity-[0.03]" fill="currentColor">
        {/* Simplified continent outlines */}
        <path d="M200,200 Q240,160 280,180 T340,200 Q360,240 320,260 T260,240 Z" /> {/* Africa */}
        <path d="M140,120 Q160,100 200,110 T240,120 Q260,160 220,170 T160,150 Z" /> {/* Europe */}
        <path d="M400,100 Q480,80 520,120 T560,160 Q540,200 480,180 T420,140 Z" /> {/* Asia */}
        <path d="M80,140 Q100,100 140,120 T160,160 Q140,200 100,180 Z" /> {/* N America */}
        <path d="M120,240 Q140,220 160,240 T180,280 Q160,320 130,300 Z" /> {/* S America */}
        <path d="M520,280 Q560,260 600,280 T620,320 Q600,340 560,320 Z" /> {/* Australia */}
        {/* Additional terrain mass */}
        <path d="M300,100 Q340,80 380,100 T420,120 Q400,140 360,130 Z" />
        <path d="M440,200 Q460,180 500,200 T520,230 Q500,250 460,240 Z" />
      </svg>
    </div>
  );
}
