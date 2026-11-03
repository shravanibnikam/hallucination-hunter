import { readFileSync } from "node:fs";
import { expect, test } from "vitest";
import { buildRound, HALLUCINATION_TYPES } from "@/lib/round-builder";
import type { PairCandidate } from "@/lib/types";

/** RFC 4180 reader: quoted fields may hold commas, doubled quotes and newlines. */
function readCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [[]];
  let field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    }
    else if (c === '"') quoted = true;
    else if (c === ",") { rows.at(-1)!.push(field); field = ""; }
    else if (c === "\n") { rows.at(-1)!.push(field.replace(/\r$/, "")); field = ""; rows.push([]); }
    else field += c;
  }
  if (field) rows.at(-1)!.push(field);
  const [header, ...body] = rows.filter(r => r.length > 1);
  return body.map(r => Object.fromEntries(header.map((h, i) => [h, r[i]])));
}
/** mulberry32, as in round-builder.test.ts, so the simulation is reproducible. */
function seeded(seed: number) {
  return () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
const pool: PairCandidate[] = readCsv(readFileSync("research/data/pairs_v1.csv", "utf8")).map(r => ({ id: r.id, category: r.category, hallucination_type: r.hallucination_type, is_active: r.is_active === "true", is_attention_check: r.is_attention_check === "true" }));
const checks = new Set(pool.filter(p => p.is_attention_check).map(p => p.id));
const byId = new Map(pool.map(p => [p.id, p]));
const count = (values: string[], value: string) => values.filter(v => v === value).length;

test("the v1 pool is 80 ordinary pairs, 20 per type, plus 4 attention checks", () => {
  const ordinary = pool.filter(p => !p.is_attention_check);
  expect(ordinary).toHaveLength(80);
  expect(checks.size).toBe(4);
  expect(HALLUCINATION_TYPES.map(t => count(ordinary.map(p => p.hallucination_type), t))).toEqual([20, 20, 20, 20]);
});

test("1,000 simulated rounds on the v1 pool keep type balance, the category cap and the single-condition split", () => {
  for (let seed = 0; seed < 1000; seed++) {
    const random = seeded(seed);
    const counts = pool.map(p => ({ pair_id: p.id, judgment_count: Math.floor(random() * 20) }));
    for (const condition of ["paired", "single"] as const) {
      const round = buildRound(pool, counts, condition, random);
      expect(round).toHaveLength(10);
      expect(round.filter(i => checks.has(i.pairId))).toHaveLength(1);
      const ordinary = round.filter(i => !checks.has(i.pairId));
      const chosen = ordinary.map(i => byId.get(i.pairId)!);
      expect(new Set(chosen.map(p => p.id)).size).toBe(9);
      for (const type of HALLUCINATION_TYPES)
        expect([2, 3]).toContain(count(chosen.map(p => p.hallucination_type), type));
      for (const category of new Set(chosen.map(p => p.category)))
        expect(count(chosen.map(p => p.category), category)).toBeLessThanOrEqual(3);
      if (condition === "single") {
        expect([4, 5]).toContain(ordinary.filter(i => i.shownAnswer === "fake").length);
        expect(round.find(i => checks.has(i.pairId))!.shownAnswer).toBe("fake");
      }
    }
  }
});
