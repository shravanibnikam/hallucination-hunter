import "server-only";
import { randomInt } from "node:crypto";
import type { TransactionSql } from "postgres";
import type { z } from "zod";
import { version } from "@/package.json";
import { db } from "./db";
import { HttpError } from "./http";
import { buildRound, type Exposure } from "./round-builder";
import { isCorrect, scoreGuesses } from "./scoring";
import { TOO_FAST_MS } from "./constants";
import type { guessSchema, sessionSchema, profileSchema } from "./schemas";
import type { Condition, PairCandidate, PublicItem, Side, Summary } from "./types";
interface SessionRow { id: string; condition: Condition; total_items: number; completed: boolean }
interface ItemRow { id: string; pair_id: string; position: number; fake_shown_on: Side | null; shown_answer: "real" | "fake" | null; served_at: Date | null; question: string; category: string; answer_real: string; answer_fake: string; fabricated_span: string; explanation: string; source_url: string | null; dataset_version: string; is_attention_check: boolean }
async function lockSession(tx: TransactionSql, id: string) { const [s] = await tx<SessionRow[]>`select id, condition, total_items, completed from sessions where id=${id} for update`; if (!s) throw new HttpError(404, "This session could not be found. Start a fresh round."); return s; }
async function item(tx: TransactionSql, id: string, position: number) { const [i] = await tx<ItemRow[]>`select i.id, i.pair_id, i.position, i.fake_shown_on, i.shown_answer, i.served_at, p.question, p.category, p.answer_real, p.answer_fake, p.fabricated_span, p.explanation, p.source_url, p.dataset_version, p.is_attention_check from session_items i join pairs p on p.id=i.pair_id where i.session_id=${id} and i.position=${position}`; if (!i) throw new HttpError(404, "Item not found."); return i; }
async function requirePrevious(tx: TransactionSql, id: string, position: number) { if (position > 1) { const [previous] = await tx`select g.id from guesses g join session_items i on i.id=g.session_item_id where g.session_id=${id} and i.position=${position - 1}`; if (!previous) throw new HttpError(409, "Answer the previous item first."); } }
async function orderedGuesses(tx: TransactionSql, id: string) { return tx<{ is_correct: boolean; is_attention_check: boolean }[]>`select g.is_correct, p.is_attention_check from guesses g join session_items i on i.id=g.session_item_id join pairs p on p.id=g.pair_id where g.session_id=${id} order by i.position`; }
export async function createSession(input: z.infer<typeof sessionSchema>) { return db().begin(async tx => { const pairs = await tx<PairCandidate[]>`select id, category, is_attention_check, is_active from pairs where is_active`; const counts = await tx<Exposure[]>`select pair_id, judgment_count from pair_exposure_counts`; const condition: Condition = randomInt(2) === 0 ? "paired" : "single"; const round = buildRound(pairs, counts, condition, () => randomInt(0, 2 ** 32) / 2 ** 32); if (!round.length) throw new HttpError(503, "The study is being prepared. Please come back soon."); const [s] = await tx<{ id: string }[]>`insert into sessions (condition, consent_given_at, age_confirmed, nickname, device_type, total_items, is_pilot, app_version) values (${condition}, now(), true, ${input.nickname ?? null}, ${input.deviceType ?? null}, ${round.length}, ${input.pilot ?? false}, ${version}) returning id`; await tx`insert into session_items ${tx(round.map(i => ({ session_id: s.id, pair_id: i.pairId, position: i.position, fake_shown_on: i.fakeShownOn, shown_answer: i.shownAnswer })))}`; return { sessionId: s.id, condition, totalItems: round.length }; }); }
export async function getItem(id: string, position: number): Promise<PublicItem> { return db().begin(async tx => { const s = await lockSession(tx,id); await requirePrevious(tx,id,position); const i = await item(tx,id,position); const [guess] = await tx`select id from guesses where session_item_id=${i.id}`; if (guess) throw new HttpError(409, "This item has already been answered."); await tx`update session_items set served_at=coalesce(served_at,now()) where id=${i.id}`; return { position, totalItems:s.total_items, question:i.question, category:i.category, display: s.condition === "single" ? { answer: i.shown_answer === "fake" ? i.answer_fake : i.answer_real } : { left: i.fake_shown_on === "left" ? i.answer_fake : i.answer_real, right: i.fake_shown_on === "right" ? i.answer_fake : i.answer_real } }; }); }
/** Lock the session and atomically write one guess; the unique constraint also prevents racing retries. */
export async function writeGuess(input: z.infer<typeof guessSchema>) { return db().begin(async tx => { const s = await lockSession(tx,input.sessionId); if ((s.condition === "paired" && (!input.chosenSide || input.judgment)) || (s.condition === "single" && (!input.judgment || input.chosenSide))) throw new HttpError(400,"Use the answer choice for your assigned condition."); const i = await item(tx,s.id,input.position); await requirePrevious(tx,s.id,input.position); if (!i.served_at) throw new HttpError(409,"Open the item before answering."); const [existing] = await tx`select id from guesses where session_item_id=${i.id}`; if (existing) throw new HttpError(409,"This item already has a guess."); const correct = isCorrect(s.condition,i,input); const ms = Math.max(0,Math.min(600000,input.responseTimeMs)); await tx`insert into guesses (session_item_id,session_id,pair_id,chosen_side,judgment,is_correct,confidence,response_time_ms,flagged_too_fast,app_version,dataset_version) values (${i.id},${s.id},${i.pair_id},${input.chosenSide ?? null},${input.judgment ?? null},${correct},${input.confidence},${ms},${ms < TOO_FAST_MS},${version},${i.dataset_version})`; const score = scoreGuesses(await orderedGuesses(tx,s.id)); return { isCorrect:correct, wasFabricated:s.condition === "paired" ? i.fake_shown_on : i.shown_answer === "fake", fabricatedAnswer:i.answer_fake, fabricatedSpan:i.fabricated_span, explanation:i.explanation, sourceUrl:i.source_url, score:score.score, currentStreak:score.currentStreak }; }); }
export async function completeSession(id: string): Promise<Summary> { return db().begin(async tx => { const s = await lockSession(tx,id); const guesses = await orderedGuesses(tx,id); if (guesses.length !== s.total_items) throw new HttpError(409,"Finish every item before completing the round."); const score = scoreGuesses(guesses); if (!s.completed) await tx`update sessions set completed=true, completed_at=now(), final_score=${score.score}, best_streak=${score.bestStreak}, failed_attention_check=${guesses.some(g => g.is_attention_check && !g.is_correct)} where id=${id}`; return { score:score.score, total:s.total_items, bestStreak:score.bestStreak }; }); }

export async function updateProfile(id: string, input: z.infer<typeof profileSchema>) {
 return db().begin(async tx => {
  await lockSession(tx,id);
  const [guess] = await tx`select id from guesses where session_id=${id} limit 1`;
  if (guess) throw new HttpError(409,"The profile can only be changed before your first guess.");
  const fields: Record<string,string | number> = {};
  if (input.aiUsageFrequency !== undefined) fields.ai_usage_frequency=input.aiUsageFrequency;
  if (input.background !== undefined) fields.background=input.background;
  if (input.aiKnowledgeRating !== undefined) fields.ai_knowledge_rating=input.aiKnowledgeRating;
  if (Object.keys(fields).length) await tx`update sessions set ${tx(fields)} where id=${id}`;
  return { saved:true };
 });
}
export async function resumeSession(id:string) {
 return db().begin(async tx => {
  const s = await lockSession(tx,id);
  const guesses = await orderedGuesses(tx,id);
  return { sessionId:id, condition:s.condition, totalItems:s.total_items, nextPosition:guesses.length < s.total_items ? guesses.length + 1 : null, currentStreak:scoreGuesses(guesses).currentStreak };
 });
}
