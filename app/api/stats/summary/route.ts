import { unstable_cache } from "next/cache";
import { db } from "@/lib/db";
import { endpoint } from "@/lib/http";
const summary=unstable_cache(async()=>{const [row]=await db()`select count(distinct s.id)::int as participants, count(g.id)::int as judgments from sessions s join guesses g on g.session_id=s.id where s.completed and not s.is_pilot`;return {totalParticipants:row.participants,totalJudgments:row.judgments};},["public-study-totals"],{revalidate:60});
export async function GET() { return endpoint(async()=>Response.json(await summary(),{headers:{"Cache-Control":"public, s-maxage=60, max-age=60"}})); }
