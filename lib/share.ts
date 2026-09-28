import { z } from "zod";
const schema=z.object({score:z.coerce.number().int().min(0).max(10),total:z.coerce.number().int().min(1).max(10)}).refine(v=>v.score<=v.total);
export function shareScore(input:{score?:unknown;total?:unknown}) { const result=schema.safeParse(input);return result.success ? result.data : null; }
