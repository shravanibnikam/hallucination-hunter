import Link from "next/link";
import { Leaderboard } from "@/components/leaderboard";
export const metadata={title:"Leaderboard · Hallucination Hunter"};
export default function Page() { return <section className="public-page"><p className="eyebrow">The sharpest eyes</p><h1>Hall of hunters.</h1><p className="lede">Top 20 rounds, ranked by score, then best streak. Earlier finishes break a tie.</p><Leaderboard /><p className="muted small">Only completed, non-pilot rounds with a nickname and a passed attention check appear here.</p><Link className="button primary" href="/play">Take your shot</Link></section>; }
