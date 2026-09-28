"use client";
import { useEffect,useState } from "react";
import { api } from "@/lib/client-api";
import type { PublicStats } from "@/lib/types";
export function StudyCounter() { const [stats,setStats]=useState<PublicStats|null>(null);useEffect(()=>{let active=true;api<PublicStats>("/api/stats/summary").then(s=>{if(active)setStats(s);}).catch(()=>{});return()=>{active=false;};},[]);return <p className="study-counter"><span className="status-dot" />{stats ? <><strong>{stats.totalJudgments.toLocaleString("en-US")}</strong> judgments collected so far</> : "Every judgment helps us understand AI."}</p>; }
