import { ImageResponse } from "next/og";
import { shareScore } from "@/lib/share";
import { designTokens as t } from "@/lib/design-tokens";
const ring = (size: number, dashed = false) => <div style={{ position: "absolute", top: 315 - size / 2, left: 900 - size / 2, width: size, height: size, borderRadius: size, border: `2px ${dashed ? "dashed" : "solid"} ${t["color-line"]}`, opacity: 0.55 }} />;
/** The share poster: the score (or the question) on the left, the landing page's worked reveal on the right. */
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const score = shareScore({ score: params.get("score") ?? undefined, total: params.get("total") ?? undefined });
  const host = process.env.APP_URL ? new URL(process.env.APP_URL).host : "";
  return new ImageResponse(<div style={{ display: "flex", position: "relative", width: "100%", height: "100%", padding: "64px 72px", background: t["color-bg"], color: t["color-ink"], fontFamily: "sans-serif" }}>
    {ring(500)}{ring(360, true)}
    <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", width: 600, height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", fontSize: t["text-og-label"], letterSpacing: 4, color: t["color-accent"] }}><div style={{ width: 14, height: 14, borderRadius: 14, background: t["color-accent"], marginRight: 16 }} />HALLUCINATION HUNTER</div>
      {score
        ? <div style={{ display: "flex", flexDirection: "column" }}><div style={{ display: "flex", alignItems: "baseline", fontSize: t["text-og-score"], fontWeight: 800, lineHeight: 1, letterSpacing: -6, color: t["color-accent"] }}>{score.score}<span style={{ fontSize: 64, color: t["color-muted"], letterSpacing: -2, marginLeft: 12 }}>/ {score.total}</span></div><div style={{ display: "flex", fontSize: 44, fontWeight: 700, marginTop: 16 }}>AI hallucinations caught</div></div>
        : <div style={{ display: "flex", fontSize: t["text-og-title"], fontWeight: 800, lineHeight: 1.05, letterSpacing: -3 }}>Can you catch the AI lying?</div>}
      <div style={{ display: "flex", fontSize: t["text-og-label"], color: t["color-muted"] }}>{score ? "Think you can beat it? " : "A game. An experiment. "}{host ? `Play at ${host}` : "Spot the made-up fact."}</div>
    </div>
    <div style={{ display: "flex", flexDirection: "column", position: "absolute", top: 175, right: 64, width: 440, padding: 32, borderRadius: 28, border: `2px solid ${t["color-line"]}`, background: t["color-panel"], transform: "rotate(3deg)" }}>
      <div style={{ display: "flex", fontSize: 18, letterSpacing: 3, color: t["color-muted"] }}>SPOT THE MADE-UP FACT</div>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", marginTop: 18, fontSize: 30, lineHeight: 1.5 }}>An octopus has<span style={{ margin: "0 10px", padding: "0 8px", borderRadius: 8, background: t["color-accent"], color: t["color-accent-ink"], textDecoration: "line-through" }}>five</span><span style={{ fontWeight: 700, color: t["color-good"], borderBottom: `3px solid ${t["color-good"]}`, marginRight: 10 }}>three</span>hearts.</div>
    </div>
  </div>, { width: 1200, height: 630 });
}
