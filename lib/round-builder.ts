import { ROUND_LENGTH } from "./constants";
import type { Condition, PairCandidate, RoundItem } from "./types";
export interface Exposure {
  pair_id: string;
  judgment_count: number | string;
}
/** Balanced in every round; "other" (index 4) only fills slots these cannot. */
export const HALLUCINATION_TYPES = ["wrong_number", "wrong_entity", "wrong_date", "invented_citation"];
const OTHER = HALLUCINATION_TYPES.length;
function shuffle<T>(values: T[], random: () => number): T[] {
  const result = [...values];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];

  }
  return result;
}
/** Hall's condition: every set of types can still meet its need from remaining pairs without overfilling a category. */
function feasible(need: number[], available: number[][], room: number[]) {
  for (let mask = 1; mask < 1 << need.length; mask++) {
    const types = need.map((_, t) => t).filter(t => mask >> t & 1);
    const demand = types.reduce((sum, t) => sum + need[t], 0);
    const supply = room.reduce((sum, r, k) => sum + Math.min(r, types.reduce((n, t) => n + available[t][k], 0)), 0);
    if (demand > supply)
      return false;

  }
  return true;
}
/** Deal slots round-robin in type order, as evenly as supply allows; the first type gets any extra. */
function quotas(order: number[], supply: number[], target: number) {
  const need = supply.map(() => 0);
  let total = 0;
  for (let added = true; added && total < target;) {
    added = false;
    for (const t of order)
      if (total < target && need[t] < supply[t]) {
        need[t]++;
        total++;
        added = true;

      }

  }
  need[OTHER] = Math.min(supply[OTHER], target - total);
  return need;
}
/** Balance hallucination types, then cap categories, preferring under-exposed facts; then randomize order and layout.
 * No database or mutable external state: all inputs and randomness are injectable.
 */
export function buildRound(pairs: PairCandidate[], counts: Exposure[], condition: Condition, random: () => number = Math.random): RoundItem[] {
  const active = [...new Map(pairs.filter(p => p.is_active).map(p => [p.id, p])).values()];
  const checks = active.filter(p => p.is_attention_check);
  const ordinary = active.filter(p => !p.is_attention_check);
  const target = Math.min(ROUND_LENGTH, ordinary.length + 1) - 1;
  const exposures = new Map(counts.map(c => [c.pair_id, Number(c.judgment_count)]));
  const ranked = shuffle(ordinary, random).sort((a, b) => (exposures.get(a.id) ?? 0) - (exposures.get(b.id) ?? 0));
  const typeOf = (p: PairCandidate) => HALLUCINATION_TYPES.includes(p.hallucination_type) ? HALLUCINATION_TYPES.indexOf(p.hallucination_type) : OTHER;
  const categories = [...new Set(ordinary.map(p => p.category))];
  const available = [...HALLUCINATION_TYPES, "other"].map(() => categories.map(() => 0));
  for (const pair of ordinary)
    available[typeOf(pair)][categories.indexOf(pair.category)]++;
  const supply = available.map(row => row.reduce((sum, n) => sum + n, 0));
  // Each type in random order gets a turn at the extra slot, so the extra stays random among types that keep the cap.
  const order = shuffle(HALLUCINATION_TYPES.map((_, t) => t), random);
  const options = order.map(first => quotas([first, ...order.filter(t => t !== first)], supply, target));
  let cap = Math.ceil(target / 3);
  const fits = (need: number[]) => feasible(need, available, categories.map(() => cap));
  let need = options.find(fits);
  // Type balance wins: raise the category cap only as far as the pool requires.
  for (; !need; need = options.find(fits))
    cap++;
  const room = categories.map(() => cap);
  const selected: PairCandidate[] = [];
  for (const pair of ranked) {
    if (selected.length === target)
      break;
    const t = typeOf(pair), k = categories.indexOf(pair.category);
    available[t][k]--;
    if (!need[t] || !room[k])
      continue;
    need[t]--;
    room[k]--;
    // Take the least-exposed pair unless doing so would make the remaining quotas impossible.
    // ponytail: greedy exposure preference; use min-cost flow if exposure must be exactly optimal under the cap.
    if (feasible(need, available, room))
      selected.push(pair);
    else {
      need[t]++;
      room[k]++;

    }

  }
  const ordered = shuffle(selected, random);
  // Single rounds show the fake on half of the ordinary items (4 or 5 of 9, chosen per round) at random positions.
  const fakes = new Set(shuffle(ordered, random).slice(0, Math.floor(ordered.length / 2) + (ordered.length % 2 && random() < .5 ? 1 : 0)).map(p => p.id));
  if (checks.length)
    ordered.splice(Math.floor(random() * (ordered.length + 1)), 0, checks[Math.floor(random() * checks.length)]);
  return ordered.map((p, i) => ({ pairId: p.id, position: i + 1, fakeShownOn: condition === "paired" ? (random() < .5 ? "left" : "right") : null, shownAnswer: condition === "single" ? (p.is_attention_check || fakes.has(p.id) ? "fake" : "real") : null }));
}
