import { ROUND_LENGTH } from "./constants";
import type { Condition, PairCandidate, RoundItem } from "./types";
export interface Exposure { pair_id: string; judgment_count: number | string }
function shuffle<T>(values: T[], random: () => number): T[] {
 const result = [...values];
 for (let i = result.length - 1; i > 0; i--) {
  const j = Math.floor(random() * (i + 1));
  [result[i], result[j]] = [result[j], result[i]];
 }
 return result;
}
/** Prefer under-exposed facts within a category cap, then randomize order and layout.
 * No database or mutable external state: all inputs and randomness are injectable.
 */
export function buildRound(pairs: PairCandidate[], counts: Exposure[], condition: Condition, random: () => number = Math.random): RoundItem[] {
 const active = [...new Map(pairs.filter(p => p.is_active).map(p => [p.id, p])).values()];
 const checks = active.filter(p => p.is_attention_check);
 const ordinary = active.filter(p => !p.is_attention_check);
 const target = Math.min(ROUND_LENGTH, ordinary.length + 1) - 1;
 const cap = Math.ceil(target / 3);
 const exposures = new Map(counts.map(c => [c.pair_id, Number(c.judgment_count)]));
 const ranked = shuffle(ordinary, random).sort((a,b) => (exposures.get(a.id) ?? 0) - (exposures.get(b.id) ?? 0));
 const selected: PairCandidate[] = [];
 const categoryCounts = new Map<string, number>();
 for (const pair of ranked) {
  if (selected.length === target) break;
  if ((categoryCounts.get(pair.category) ?? 0) >= cap) continue;
  selected.push(pair);
  categoryCounts.set(pair.category, (categoryCounts.get(pair.category) ?? 0) + 1);
 }
 // Relax only when the available categories cannot fill a round under the cap.
 const ids = new Set(selected.map(p => p.id));
 for (const pair of ranked) {
  if (selected.length === target) break;
  if (!ids.has(pair.id)) { selected.push(pair); ids.add(pair.id); }
 }
 const ordered = shuffle(selected,random);
 if (checks.length) ordered.splice(Math.floor(random() * (ordered.length + 1)), 0, checks[Math.floor(random() * checks.length)]);
 return ordered.map((p,i) => ({ pairId:p.id, position:i+1, fakeShownOn:condition === "paired" ? (random() < .5 ? "left" : "right") : null, shownAnswer:condition === "single" ? (p.is_attention_check || random() < .5 ? "fake" : "real") : null }));
}
