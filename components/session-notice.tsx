"use client";
import { useSyncExternalStore } from "react";
const subscribe = () => () => {};
export function SessionNotice() { const missing = useSyncExternalStore(subscribe,()=>new URLSearchParams(window.location.search).get("session")==="missing",()=>false); return missing ? <p className="panel" role="status">We couldn’t find that session. You can start a fresh hunt below.</p> : null; }
