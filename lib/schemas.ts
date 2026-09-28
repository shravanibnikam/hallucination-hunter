import { z } from "zod";
const blocked = new Set(["fuck", "shit", "asshole", "bitch", "bastard"]);
export const nicknameSchema = z.string().trim().min(2).max(20).regex(/^[A-Za-z0-9 _-]+$/).refine(value => !value.toLowerCase().split(/[ _-]+/).some(word => blocked.has(word)), "Please choose another nickname.");
export const sessionSchema = z.object({ consent: z.literal(true), ageConfirmed: z.literal(true), nickname: nicknameSchema.optional(), deviceType: z.enum(["mobile", "desktop"]).optional(), pilot: z.boolean().optional() }).strict();
export const profileSchema = z.object({ aiUsageFrequency: z.enum(["never", "monthly", "weekly", "daily"]).optional(), background: z.enum(["cs_engineering", "other_stem", "non_stem", "prefer_not_to_say"]).optional(), aiKnowledgeRating: z.number().int().min(1).max(5).optional() }).strict();
export const guessSchema = z.object({ sessionId: z.uuid(), position: z.number().int().min(1).max(10), chosenSide: z.enum(["left", "right"]).optional(), judgment: z.enum(["yes", "no"]).optional(), confidence: z.number().int().min(1).max(5), responseTimeMs: z.number().int().min(-Number.MAX_SAFE_INTEGER).max(Number.MAX_SAFE_INTEGER) }).strict().refine(data => Boolean(data.chosenSide) !== Boolean(data.judgment), "Supply exactly one answer choice.");
export const emptySchema = z.object({}).strict();
export const idSchema = z.uuid();
export const positionSchema = z.coerce.number().int().min(1).max(10);
