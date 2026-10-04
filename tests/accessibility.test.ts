import { expect, test } from "vitest";
import { designTokens as t } from "@/lib/design-tokens";
function luminance(hex: string) {
  const rgb = hex.slice(1).match(/../g)!.map(c => parseInt(c, 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
  return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
}
function contrast(a: string, b: string) {
  const x = luminance(a), y = luminance(b);
  return (Math.max(x, y) + .05) / (Math.min(x, y) + .05);
}
test("text and control colors meet AA contrast", () => {
  for (const background of [t['color-bg'], t['color-panel'], t['color-panel-hover']]) {
    for (const text of [t['color-ink'], t['color-muted'], t['color-accent'], t['color-good'], t['color-bad']])
      expect(contrast(text, background)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(t['color-line'], background)).toBeGreaterThanOrEqual(3);
  }
  expect(contrast(t['color-accent-ink'], t['color-accent'])).toBeGreaterThanOrEqual(4.5);
});
