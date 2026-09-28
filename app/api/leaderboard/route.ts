import { db } from "@/lib/db";
import { endpoint,json } from "@/lib/http";
export async function GET() { return endpoint(async()=>{const rows=await db()`select nickname, final_score, total_items, best_streak from sessions where completed and not is_pilot and failed_attention_check=false and nickname is not null order by final_score desc, best_streak desc, completed_at asc limit 20`;return json(rows.map(r=>({nickname:r.nickname,score:r.final_score,total:r.total_items,bestStreak:r.best_streak})));}); }
