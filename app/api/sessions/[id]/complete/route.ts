import { body, endpoint, json } from "@/lib/http";
import { emptySchema, idSchema } from "@/lib/schemas";
import { completeSession } from "@/lib/game-service";
export async function POST(request: Request, context: { params: Promise<{ id: string }> }) { return endpoint(async () => { await body(request,emptySchema); return json(await completeSession(idSchema.parse((await context.params).id))); }); }
