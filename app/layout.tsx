import { themeStyles } from "@/lib/design-tokens";
import type { CSSProperties } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { ScanEye } from "lucide-react";
import "./globals.css";
export const metadata: Metadata = { title: "Hallucination Hunter", description: "Can you catch the AI lying? Play a game. Help a study." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en" style={themeStyles as CSSProperties}><body><a className="skip-link" href="#main">Skip to content</a><header className="site-header"><Link href="/" className="brand"><ScanEye aria-hidden="true" /> Hallucination<span>Hunter</span></Link><span className="eyebrow">A human × AI study</span></header><main id="main">{children}</main><footer>Built for curious minds. <Link href="/about">About the study</Link><Link href="/privacy">Privacy</Link><Link href="/leaderboard">Leaderboard</Link></footer></body></html>; }
