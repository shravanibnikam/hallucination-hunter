// Single source of truth for the app and generated share images.
export const designTokens = {
  "color-bg": "#101210",
  "color-panel": "#191d19",
  "color-panel-hover": "#232a21",
  "color-ink": "#f4f6ef",
  "color-muted": "#aeb7aa",
  "color-line": "#65735e",
  "color-accent": "#c0f46a",
  "color-accent-ink": "#17200c",
  "color-good": "#b5f28a",
  "color-bad": "#ffb1a7",
  "radius-sm": "0.5rem",
  "radius-card": "1.25rem",
  "radius-pill": "100rem",
  "text-xs": ".75rem",
  "text-sm": ".875rem",
  "text-base": "1rem",
  "text-lg": "1.125rem",
  "text-xl": "1.5rem",
  "text-2xl": "2rem",
  "text-hero": "clamp(3rem, 8vw, 6rem)",
  "font-sans": "Arial, Helvetica, sans-serif",
  "text-display": "clamp(2rem, 6vw, 3.5rem)",
  "text-og-title": "80px",
  "text-og-label": "28px",
  "text-og-score": "140px"
} as const;
export const themeStyles = Object.fromEntries(Object.entries(designTokens).map(([key,value]) => [`--token-${key}`,value]));
