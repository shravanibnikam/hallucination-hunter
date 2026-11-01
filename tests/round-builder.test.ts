import { expect, test } from "vitest";
import { buildRound } from "@/lib/round-builder";
import { isCorrect } from "@/lib/scoring";
import { profileSchema } from "@/lib/schemas";
import type { PairCandidate } from "@/lib/types";
const types = ["wrong_number", "wrong_entity", "wrong_date", "invented_citation"];
const categories = ["science", "history", "geography"];
const ordinary: PairCandidate[] = Array.from({ length: 30 }, (_, i) => ({ id: `p${i}`, category: categories[i % 3], hallucination_type: types[i % 4], is_active: true, is_attention_check: false }));
const check: PairCandidate = { id: "check", category: "science", hallucination_type: "other", is_active: true, is_attention_check: true };
/** mulberry32: a tiny seeded generator so 1,000-round properties are reproducible. */
function seeded(seed: number) {
  return () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
const tally = (values: string[]) => values.reduce((m, v) => m.set(v, (m.get(v) ?? 0) + 1), new Map<string, number>());
function picked(pool: PairCandidate[], round: { pairId: string }[]) {
  return round.filter(i => i.pairId !== check.id).map(i => pool.find(p => p.id === i.pairId)!);
}
test("exact length, no repeats, exactly one attention check", () => {
  for (const size of [0, 1, 5, 30]) {
    const round = buildRound([...ordinary.slice(0, size), check, { ...check, id: "check2" }], [], "paired");
    expect(round).toHaveLength(Math.min(10, size + 1));
    expect(new Set(round.map(i => i.pairId)).size).toBe(round.length);
    expect(round.filter(i => i.pairId.startsWith("check"))).toHaveLength(1);
    expect(round.map(i => i.position)).toEqual(round.map((_, i) => i + 1));
  }
});
test("lowest exposure wins within each type", () => {
  const pool = ordinary.map(p => ({ ...p, category: "science" }));
  const counts = pool.map((p, i) => ({ pair_id: p.id, judgment_count: i < 12 ? 0 : 100 }));
  for (let seed = 0; seed < 50; seed++)
    expect(picked(pool, buildRound([...pool, check], counts, "paired", seeded(seed))).every(p => Number(p.id.slice(1)) < 12)).toBe(true);
});
test("every round has each hallucination type 2 or 3 times and respects the category cap", () => {
  const pool = types.flatMap(type => categories.flatMap(category => Array.from({ length: 4 }, (_, i) => ({ id: `${type}-${category}-${i}`, category, hallucination_type: type, is_active: true, is_attention_check: false }))));
  const extra = new Map<string, number>();
  for (let seed = 0; seed < 1000; seed++) {
    const random = seeded(seed);
    const counts = pool.map(p => ({ pair_id: p.id, judgment_count: Math.floor(random() * 5) }));
    const round = buildRound([...pool, check], counts, "paired", random);
    expect(round).toHaveLength(10);
    const chosen = picked(pool, round);
    const byType = tally(chosen.map(p => p.hallucination_type));
    expect(types.map(t => byType.get(t) ?? 0).sort()).toEqual([2, 2, 2, 3]);
    expect([...tally(chosen.map(p => p.category)).values()].every(n => n <= 3)).toBe(true);
    const three = types.find(t => byType.get(t) === 3)!;
    extra.set(three, (extra.get(three) ?? 0) + 1);
  }
  // The extra slot goes to a randomly chosen type, not a fixed one.
  expect(types.every(t => (extra.get(t) ?? 0) > 150)).toBe(true);
});
test("category cap holds whenever the pool allows it, even when a type lives in one category", () => {
  // Citations exist only in science, and science is least exposed: a greedy pick would fill science first.
  const pool = [...types.slice(0, 3).flatMap(type => categories.flatMap(category => Array.from({ length: 3 }, (_, i) => ({ id: `${type}-${category}-${i}`, category, hallucination_type: type, is_active: true, is_attention_check: false })))), ...Array.from({ length: 3 }, (_, i) => ({ id: `cite-${i}`, category: "science", hallucination_type: "invented_citation", is_active: true, is_attention_check: false }))];
  const counts = pool.map(p => ({ pair_id: p.id, judgment_count: p.category === "science" ? 0 : 100 }));
  for (let seed = 0; seed < 1000; seed++) {
    const chosen = picked(pool, buildRound([...pool, check], counts, "paired", seeded(seed)));
    expect(chosen).toHaveLength(9);
    expect(tally(chosen.map(p => p.category)).get("science")).toBe(3);
    expect(tally(chosen.map(p => p.hallucination_type)).get("invented_citation")).toBeGreaterThanOrEqual(2);
  }
});
test("type balance wins when the category cap cannot also be met", () => {
  const pool = ordinary.map(p => ({ ...p, category: "science" }));
  for (let seed = 0; seed < 100; seed++) {
    const chosen = picked(pool, buildRound([...pool, check], [], "paired", seeded(seed)));
    expect(chosen).toHaveLength(9);
    expect(types.map(t => tally(chosen.map(p => p.hallucination_type)).get(t)).sort()).toEqual([2, 2, 2, 3]);
  }
});
test("other-type pairs only fill slots the four types cannot, and types never leave the server", () => {
  const others = Array.from({ length: 10 }, (_, i) => ({ id: `o${i}`, category: categories[i % 3], hallucination_type: "other", is_active: true, is_attention_check: false }));
  const counts = others.map(p => ({ pair_id: p.id, judgment_count: 0 })).concat(ordinary.map(p => ({ pair_id: p.id, judgment_count: 100 })));
  const round = buildRound([...others, ...ordinary, check], counts, "paired", seeded(1));
  expect(round.some(i => i.pairId.startsWith("o"))).toBe(false);
  expect(Object.keys(round[0]).sort()).toEqual(["fakeShownOn", "pairId", "position", "shownAnswer"]);
  const scarce = [...others, ...ordinary.filter(p => p.hallucination_type === "wrong_date")];
  const chosen = picked(scarce, buildRound([...scarce, check], [], "paired", seeded(2)));
  expect(tally(chosen.map(p => p.hallucination_type)).get("wrong_date")).toBe(7);
  expect(chosen).toHaveLength(9);
});
test("category cap overrides exposure preference and relaxes only for scarce categories", () => {
  const counts = ordinary.map(p => ({ pair_id: p.id, judgment_count: p.category === "science" ? 0 : 100 }));
  const r = buildRound([...ordinary, check], counts, "paired");
  for (const category of ["science", "history", "geography"])
    expect(r.filter(i => ordinary.find(p => p.id === i.pairId)?.category === category)).toHaveLength(3);
  expect(buildRound([...ordinary.map(p => ({ ...p, category: "science" })), check], [], "paired")).toHaveLength(10);
});
test("single attention checks always fake; inactive and duplicate pairs excluded", () => {
  const r = buildRound([...ordinary, ordinary[0], check, { ...check, id: "inactive", is_active: false }], [], "single", () => .99);
  expect(r.find(i => i.pairId === "check")?.shownAnswer).toBe("fake");
  expect(r.every(i => i.fakeShownOn === null)).toBe(true);
  expect(r.filter(i => i.pairId !== "check").every(i => i.shownAnswer === "real")).toBe(true);
  expect(r.some(i => i.pairId === "inactive")).toBe(false);
});
test("missing attention check shortens round", () => {
  expect(buildRound(ordinary, [], "paired")).toHaveLength(9);
  expect(buildRound([], [], "single")).toEqual([]);
});
test("random ties and layouts can differ", () => {
  expect(buildRound([...ordinary, check], [], "paired", () => 0)).not.toEqual(buildRound([...ordinary, check], [], "paired", () => .99));
});
test("single correctness truth table", () => {
  for (const shown of ["real", "fake"] as const)
    for (const judgment of ["yes", "no"] as const)
      expect(isCorrect("single", { shown_answer: shown, fake_shown_on: null }, { judgment })).toBe((shown === "fake") === (judgment === "yes"));
  expect(isCorrect("single", { shown_answer: "real", fake_shown_on: null }, {})).toBe(false);
});
test("profile validates optional fields and ranges", () => {
  expect(profileSchema.safeParse({}).success).toBe(true);
  for (const data of [{ aiKnowledgeRating: 0 }, { aiUsageFrequency: "hourly" }, { background: "secret" }, { aiKnowledgeRating: "3" }, { extra: true }])
    expect(profileSchema.safeParse(data).success).toBe(false);
});
