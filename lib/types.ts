export type Condition = "paired" | "single";
export type Side = "left" | "right";
export type Judgment = "yes" | "no";
export interface PairCandidate { id: string; category: string; is_attention_check: boolean; is_active: boolean }
export interface RoundItem { pairId: string; position: number; fakeShownOn: Side | null; shownAnswer: "real" | "fake" | null }
export interface PublicItem { position: number; totalItems: number; question: string; category: string; display: { left: string; right: string } | { answer: string } }
export interface SessionInfo { sessionId: string; condition: Condition; totalItems: number }
export interface Reveal { isCorrect: boolean; wasFabricated: Side | boolean; fabricatedAnswer: string; fabricatedSpan: string; explanation: string; sourceUrl: string | null; score: number; currentStreak: number }
export interface Summary { score: number; total: number; bestStreak: number }

export interface ResumeInfo extends SessionInfo { nextPosition: number | null; currentStreak: number }
