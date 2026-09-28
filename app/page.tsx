import { SessionNotice } from "@/components/session-notice";
import Link from "next/link";
import { ArrowRight, ScanEye } from "lucide-react";
export default function Home() { return <section className="hero"><SessionNotice /><p className="eyebrow"><span className="status-dot" /> A game. An experiment. A reality check.</p><h1>Can you catch<br />the AI <span>lying?</span></h1><p className="lede">Sounds convincing. Might be completely made up.<br />Put your instincts to the test and help us study how humans spot AI hallucinations.</p><Link className="button primary" href="/play">Start the hunt <ArrowRight aria-hidden="true" /></Link><div className="hero-note"><ScanEye size={16} aria-hidden="true" /> Anonymous research · Ages 18+</div></section>; }
