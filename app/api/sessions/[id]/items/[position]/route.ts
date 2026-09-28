import { endpoint, json } from "@/lib/http";
import { idSchema, positionSchema } from "@/lib/schemas";
import { getItem } from "@/lib/game-service";
export async function GET(_request: Request, context: { params: Promise<{ id: string; position: string }> }) { return endpoint(async () => { const p = await context.params; return json(await getItem(idSchema.parse(p.id),positionSchema.parse(p.position))); }); }
