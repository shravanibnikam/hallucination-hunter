import { ROUND_LENGTH } from "./constants";
import type { PairCandidate, RoundItem } from "./types";
/** Pure round construction: inject randomness to make assignment reproducible in tests. */
export function buildRound(pairs: PairCandidate[], random: () => number = Math.random): RoundItem[] {
 const pool = [...new Map(pairs.filter(p => p.is_active && !p.is_attention_check).map(p => [p.id, p])).values()];
 for (let i = pool.length - 1; i > 0; i--) { const j = Math.floor(random() * (i + 1)); [pool[i], pool[j]] = [pool[j], pool[i]]; }
 return pool.slice(0, ROUND_LENGTH).map((p, i) => ({ pairId: p.id, position: i + 1, fakeShownOn: random() < .5 ? "left" : "right", shownAnswer: null }));
}
