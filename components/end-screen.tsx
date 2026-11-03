"use client";
import { useEffect, useRef } from "react";
import Link from "next/link";
import { Check, Flame, ArrowRight } from "lucide-react";
import { statedProbability } from "@/lib/calibration";
import { MIN_COMPARISON_PLAYERS } from "@/lib/constants";
import type { CategoryAccuracy, Summary } from "@/lib/types";
import { ShareButton } from "./share-button";
const percent = (n: number) => `${Math.round(n)}%`;
/** Your accuracy per category, beside the average player's once enough people have played. */
function CategoryBars({ rows }: { rows: CategoryAccuracy[] }) {
  const compared = rows.some(r => r.averageAccuracy !== null);
  return <>{compared && <p className="chart-legend" aria-hidden="true"><span><i className="key you" />You</span><span><i className="key players" />Average player</span></p>}{rows.map(r => <div className="bar-row" key={r.category}><span className="bar-label">{r.category}</span><div className="bar-line"><span className="bar-plot" aria-hidden="true"><span className="bar you" style={{ width: `${r.accuracy}%` }} /></span><span className="bar-value"><span className="sr-only">You: </span>{r.correct} / {r.total} · {percent(r.accuracy)}</span></div>{r.averageAccuracy !== null && <div className="bar-line"><span className="bar-plot" aria-hidden="true"><span className="bar players" style={{ width: `${r.averageAccuracy}%` }} /></span><span className="bar-value muted"><span className="sr-only">Average player: </span>{percent(r.averageAccuracy)}</span></div>}</div>)}{!compared && <p className="muted small">The average player appears here once {MIN_COMPARISON_PLAYERS} people have played.</p>}</>;
}
/** Accuracy at each confidence level against what a well-calibrated player would score there. */
function ConfidenceChart({ levels }: { levels: Summary["calibration"]["byConfidence"] }) {
  return <figure className="conf-chart"><p className="chart-legend" aria-hidden="true"><span><i className="key you" />Your accuracy</span><span><i className="key target" />If well calibrated</span></p><div className="conf-plot"><span className="conf-axis" aria-hidden="true"><span>100%</span><span>50%</span><span>0%</span></span>{levels.map(l => {
    const tip = l.total ? `Confidence ${l.confidence}: ${l.correct} of ${l.total} correct (${percent(l.correct / l.total * 100)}). Well calibrated: ${percent(statedProbability(l.confidence))}.` : `Confidence ${l.confidence}: not used this round. Well calibrated: ${percent(statedProbability(l.confidence))}.`;
    return <div className="conf-col" key={l.confidence} tabIndex={0} aria-label={tip} data-tip={tip}><span className="conf-area" aria-hidden="true">{l.total > 0 && <span className="conf-bar" style={{ height: `${l.correct / l.total * 100}%` }} />}<span className="conf-target" style={{ bottom: `${statedProbability(l.confidence)}%` }} /></span><span className="conf-label" aria-hidden="true">{l.confidence}</span><span className="conf-n muted" aria-hidden="true">{l.total ? `${l.correct}/${l.total}` : "–"}</span></div>;
  })}</div><figcaption className="muted small">Confidence from 1 (pure guess) to 5 (certain). Numbers show correct answers out of guesses at each level.</figcaption></figure>;
}
export function EndScreen({ summary }: { summary: Summary }) {
  const title=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{title.current?.focus();},[]);
  return <section className="end-screen"><span className="icon-orbit"><Check aria-hidden="true" /></span><p className="eyebrow">Round complete</p><h1 ref={title} tabIndex={-1}>Good eye, human.</h1><p className="muted">Every guess helps us understand what makes a lie convincing.</p><p className="score">{summary.score}<span> / {summary.total}</span></p><p className="streak"><Flame size={16} aria-hidden="true" />Best streak: {summary.bestStreak}</p><div className="result-grid"><section className="panel"><p className="eyebrow">Your eye for detail</p><h2>By category</h2><CategoryBars rows={summary.accuracyPerCategory} /></section><section className="panel"><p className="eyebrow">Confidence meets reality</p><h2>A little gut check</h2><p>{summary.calibration.message}</p><ConfidenceChart levels={summary.calibration.byConfidence} /><p className="muted small">{summary.averageConfidence !== null ? `Average confidence: ${summary.averageConfidence.toFixed(1)} / 5. ` : ""}Category and confidence insights exclude the attention check. A fun insight, not a judgment.</p></section></div><div className="end-actions"><ShareButton score={summary.score} total={summary.total} /><button className="button" onClick={() => {
    sessionStorage.removeItem("hunter-session");
    window.location.reload();
  }}>Play again <ArrowRight size={18} aria-hidden="true" /></button></div><Link href="/leaderboard">View leaderboard →</Link></section>;
}
