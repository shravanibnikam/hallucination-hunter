import { beforeAll, beforeEach, afterAll, expect, test, vi } from "vitest";
import postgres from "postgres";
import { POST as create } from "@/app/api/sessions/route";
import { POST as guess } from "@/app/api/guesses/route";
import { GET as getItem } from "@/app/api/sessions/[id]/items/[position]/route";
import { POST as complete } from "@/app/api/sessions/[id]/complete/route";
import { PATCH as profile } from "@/app/api/sessions/[id]/profile/route";
import { GET as resume } from "@/app/api/sessions/[id]/route";
import { GET as leaderboard } from "@/app/api/leaderboard/route";
import { GET as stats } from "@/app/api/stats/summary/route";
import { db } from "@/lib/db";
import type { Condition, SessionInfo } from "@/lib/types";
vi.mock("next/cache", () => ({ unstable_cache: (fn: unknown) => fn }));
const url = process.env.TEST_DATABASE_URL;
if (!url || !new URL(url).pathname.endsWith("_test"))
  throw new Error("Set TEST_DATABASE_URL to a disposable database whose name ends in _test; never use production.");
process.env.DATABASE_URL = url;
const sql = postgres(url, { max: 3, prepare: false });
const request = (data: unknown, method = "POST") => new Request("http://local/api", { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
const context = (id: string) => ({ params: Promise.resolve({ id }) });
const itemContext = (id: string, position: number) => ({ params: Promise.resolve({ id, position: String(position) }) });
const get = (id: string, position: number) => getItem(new Request("http://local"), itemContext(id, position));
async function session(condition: Condition = "paired", extra: Record<string, unknown> = {}) {
  const response = await create(request({ consent: true, ageConfirmed: true, ...extra }));
  expect(response.status).toBe(201);
  const s = await response.json() as SessionInfo;
  // Test-fixture assignment only, before serving anything. No public override exists.
  await sql`update sessions set condition=${condition} where id=${s.sessionId}`;
  if (condition === "paired")
    await sql`update session_items set fake_shown_on=case when position%2=0 then 'left' else 'right' end, shown_answer=null where session_id=${s.sessionId}`;
  else
    await sql`update session_items i set fake_shown_on=null, shown_answer=case when p.is_attention_check or position%2=0 then 'fake' else 'real' end from pairs p where p.id=i.pair_id and i.session_id=${s.sessionId}`;
  return { ...s, condition };
}
async function answer(s: SessionInfo, position: number, correct = true, ms = 2000) {
  expect((await get(s.sessionId, position)).status).toBe(200);
  const [layout] = await sql`select fake_shown_on,shown_answer from session_items where session_id=${s.sessionId} and position=${position}`;
  const chosen = correct ? layout.fake_shown_on : layout.fake_shown_on === "left" ? "right" : "left";
  const judgment = (layout.shown_answer === "fake") === correct ? "yes" : "no";
  return guess(request({ sessionId: s.sessionId, position, ...s.condition === "paired" ? { chosenSide: chosen } : { judgment }, confidence: 4, responseTimeMs: ms }));
}
beforeAll(async () => {
  await sql`truncate guesses,session_items,sessions,pairs`;
  for (let i = 1; i <= 14; i++)
    await sql`insert into pairs(question,category,answer_real,answer_fake,fabricated_span,hallucination_type,explanation,origin,is_attention_check,dataset_version) values (${`[SAMPLE] Fixture ${i}: is two plus two four?`},${["science", "history", "geography"][i % 3]},'Two plus two is four.','Two plus two is five.','five','wrong_number','Two plus two is four.','synthetic',${i > 12},'test-v0')`;
});
beforeEach(async () => {
  await sql`truncate guesses,session_items,sessions`;
});
afterAll(async () => {
  await db().end();
  await sql.end();
});
for (const condition of ["paired", "single"] as const) {
  test(`${condition}: item response contains only unlabeled display data`, async () => {
    const s = await session(condition);
    const response = await get(s.sessionId, 1);
    expect(response.status).toBe(200);
    const payload = await response.json();
    expect(Object.keys(payload).sort()).toEqual(["category", "display", "position", "question", "totalItems"]);
    expect(Object.keys(payload.display).sort()).toEqual(condition === "paired" ? ["left", "right"] : ["answer"]);
    const json = JSON.stringify(payload);
    for (const key of ["answer_real", "answer_fake", "fabricated_span", "explanation", "fake_shown_on", "shown_answer", "pair_id", "dataset_version", "is_attention_check"])
      expect(json).not.toContain(key);
    const [first] = await sql`select served_at from session_items where session_id=${s.sessionId} and position=1`;
    await get(s.sessionId, 1);
    const [again] = await sql`select served_at from session_items where session_id=${s.sessionId} and position=1`;
    expect(again.served_at).toEqual(first.served_at);
    expect((await get(s.sessionId, 2)).status).toBe(409);

  });
  test(`${condition}: duplicate concurrent guesses cannot overwrite the first`, async () => {
    const s = await session(condition);
    await get(s.sessionId, 1);
    const input = { sessionId: s.sessionId, position: 1, ...condition === "paired" ? { chosenSide: "left" } : { judgment: "yes" }, confidence: 3, responseTimeMs: 2000 };
    const results = await Promise.all([guess(request(input)), guess(request(input))]);
    expect(results.map(r => r.status).sort()).toEqual([200, 409]);
    const [count] = await sql`select count(*)::int as n from guesses where session_id=${s.sessionId}`;
    expect(count.n).toBe(1);

  });
  test(`${condition}: completion requires every guess and computes an idempotent summary`, async () => {
    const s = await session(condition, { nickname: "Test Hunter" });
    expect((await complete(request({}), context(s.sessionId))).status).toBe(409);
    let expected = 0;
    for (let i = 1; i <= s.totalItems; i++) {
      const correct = i % 3 !== 0;
      expected += Number(correct);
      const response = await answer(s, i, correct);
      expect(response.status).toBe(200);
      const reveal = await response.json();
      expect(reveal.isCorrect).toBe(correct);
      expect(reveal.score).toBe(expected);
      expect(reveal.fabricatedAnswer).toContain(reveal.fabricatedSpan);
      if (condition === "single")
        expect(typeof reveal.wasFabricated).toBe("boolean");

    }
    const summary = await (await complete(request({}), context(s.sessionId))).json();
    expect(summary).toMatchObject({ score: expected, total: 10, bestStreak: 2 });
    expect(summary.accuracyPerCategory.reduce((n: number, c: {
      total: number;
    }) => n + c.total, 0)).toBe(9);
    const [stored] = await sql`select * from sessions where id=${s.sessionId}`;
    expect(stored.final_score).toBe(expected);
    expect(stored.completed).toBe(true);
    const [attention] = await sql`select g.is_correct from guesses g join pairs p on p.id=g.pair_id where g.session_id=${s.sessionId} and p.is_attention_check`;
    expect(stored.failed_attention_check).toBe(!attention.is_correct);
    expect(await (await complete(request({}), context(s.sessionId))).json()).toEqual(summary);
    const [again] = await sql`select completed_at from sessions where id=${s.sessionId}`;
    expect(again.completed_at).toEqual(stored.completed_at);

  });
}
test("invalid consent, client scores, malformed IDs, and wrong-condition choices fail", async () => {
  expect((await create(request({ consent: false, ageConfirmed: true }))).status).toBe(400);
  const s = await session();
  await get(s.sessionId, 1);
  for (const extra of [{ judgment: "yes" }, { chosenSide: "left", score: 10 }])
    expect((await guess(request({ sessionId: s.sessionId, position: 1, confidence: 3, responseTimeMs: 1000, ...extra }))).status).toBe(400);
  expect((await get("bad-id", 1)).status).toBe(400);
  expect((await get("00000000-0000-4000-8000-000000000999", 1)).status).toBe(404);
  const other = await session();
  expect((await guess(request({ sessionId: other.sessionId, position: 1, chosenSide: "left", confidence: 2, responseTimeMs: 2000 }))).status).toBe(409);
});
test("timing is clamped and fast responses are flagged", async () => {
  const s = await session();
  await answer(s, 1, true, -100);
  await answer(s, 2, true, 900000);
  const rows = await sql`select g.response_time_ms,g.flagged_too_fast from guesses g join session_items i on i.id=g.session_item_id where g.session_id=${s.sessionId} order by i.position`;
  expect(rows.map(r => [r.response_time_ms, r.flagged_too_fast])).toEqual([[0, true], [600000, false]]);
});
test("profiles lock after first guess and refresh returns next unguessed item", async () => {
  const s = await session();
  expect((await profile(request({ aiUsageFrequency: "daily", aiKnowledgeRating: 4 }, "PATCH"), context(s.sessionId))).status).toBe(200);
  await answer(s, 1);
  expect((await profile(request({ background: "non_stem" }, "PATCH"), context(s.sessionId))).status).toBe(409);
  expect(await (await resume(new Request("http://local"), context(s.sessionId))).json()).toMatchObject({ nextPosition: 2, currentStreak: 1, condition: "paired" });
});
test("pilot guesses do not affect exposure or public totals and leaderboards exclude disqualified sessions", async () => {
  const normal = await session("paired", { nickname: "Public Hunter" });
  for (let i = 1; i <= 10; i++)
    await answer(normal, i);
  await complete(request({}), context(normal.sessionId));
  const [exposure] = await sql`select sum(judgment_count)::int as n from pair_exposure_counts`;
  expect(exposure.n).toBe(10);
  const pilot = await session("single", { pilot: true, nickname: "Pilot Hunter" });
  for (let i = 1; i <= 10; i++)
    await answer(pilot, i);
  await complete(request({}), context(pilot.sessionId));
  const failed = await session("paired", { nickname: "Failed Hunter" });
  for (let i = 1; i <= 10; i++)
    await answer(failed, i, false);
  await complete(request({}), context(failed.sessionId));
  const anonymous = await session("single");
  for (let i = 1; i <= 10; i++)
    await answer(anonymous, i);
  await complete(request({}), context(anonymous.sessionId));
  const rows = await (await leaderboard()).json();
  expect(rows).toEqual([{ nickname: "Public Hunter", score: 10, total: 10, bestStreak: 10 }]);
  const summary = await stats();
  expect(summary.headers.get("cache-control")).toContain("60");
  expect(await summary.json()).toEqual({ totalParticipants: 3, totalJudgments: 30 });
  const [total] = await sql`select sum(judgment_count)::int as n from pair_exposure_counts`;
  expect(total.n).toBe(30);
  const [stored] = await sql`select is_pilot from sessions where id=${pilot.sessionId}`;
  expect(stored.is_pilot).toBe(true);
});
test("assigned facts cannot be edited, but can be deactivated", async () => {
  const s = await session();
  const [i] = await sql`select pair_id from session_items where session_id=${s.sessionId} limit 1`;
  await expect(sql`update pairs set answer_real='Changed' where id=${i.pair_id}`).rejects.toThrow("immutable");
  await sql`update pairs set is_active=false where id=${i.pair_id}`;
  await sql`update pairs set is_active=true where id=${i.pair_id}`;
});
test("RLS is enabled with zero public policies and invoker-safe exposure view", async () => {
  const tables = await sql`select relname,relrowsecurity from pg_class where oid in ('pairs'::regclass,'sessions'::regclass,'session_items'::regclass,'guesses'::regclass)`;
  expect(tables).toHaveLength(4);
  expect(tables.every(t => t.relrowsecurity)).toBe(true);
  const policies = await sql`select * from pg_policies where schemaname='public' and tablename in ('pairs','sessions','session_items','guesses')`;
  expect(policies).toHaveLength(0);
  for (const role of ["anon", "authenticated"]) {
    await sql.unsafe(`do $$ begin if not exists(select from pg_roles where rolname='${role}') then create role ${role} nologin; end if; end $$`);
    await sql.begin(async (tx) => {
      await tx.unsafe(`grant usage on schema public to ${role}`);
      await tx.unsafe(`grant select on pairs,sessions,session_items,guesses,pair_exposure_counts to ${role}`);
      await tx.unsafe(`set local role ${role}`);
      for (const table of ["pairs", "sessions", "session_items", "guesses", "pair_exposure_counts"])
        expect(await tx.unsafe(`select * from ${table}`)).toHaveLength(0);
      await tx`reset role`;
      await tx.unsafe(`revoke all on pairs,sessions,session_items,guesses,pair_exposure_counts from ${role}`);

    });

  }
});
test("rounds without an attention check cannot qualify for the leaderboard", async () => {
  await sql`update pairs set is_active=false where is_attention_check`;
  try {
    const s=await session("paired",{nickname:"No Check Hunter"});
    expect(s.totalItems).toBe(9);
    for(let i=1;i<=s.totalItems;i++)expect((await answer(s,i)).status).toBe(200);
    expect((await complete(request({}),context(s.sessionId))).status).toBe(200);
    expect(await (await leaderboard()).json()).toEqual([]);
  } finally {
    await sql`update pairs set is_active=true where is_attention_check`;
  }
});
