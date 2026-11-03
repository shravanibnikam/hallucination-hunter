"use client";
import { useState } from "react";
import { CheckCircle2, RotateCcw } from "lucide-react";
/** A worked example of the reveal on a fact that is not in the study, played once and replayable. */
export function DemoItem() {
  const [run, setRun] = useState(0);
  return <div className="demo"><div className="demo-card panel" key={run}><p className="eyebrow">Example · not part of the study</p><p className="demo-question">How many hearts does an octopus have?</p><p className="fabricated demo-answer">An octopus has <del><span className="sr-only">fabricated: </span><mark>five</mark></del><ins><span className="sr-only">, real value: </span>three</ins> hearts: two pump blood through its gills and one pumps it around the rest of its body.</p><p className="demo-verdict"><CheckCircle2 size={18} aria-hidden="true" /> Spot the made-up fact.</p></div><button className="demo-replay" onClick={() => setRun(n => n + 1)}><RotateCcw size={14} aria-hidden="true" /> Replay the example</button></div>;
}
