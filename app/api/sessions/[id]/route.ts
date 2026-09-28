import { endpoint, json } from "@/lib/http";
import { idSchema } from "@/lib/schemas";
import { resumeSession } from "@/lib/game-service";
export async function GET(_request:Request, context:{params:Promise<{id:string}>}) { return endpoint(async () => json(await resumeSession(idSchema.parse((await context.params).id)))); }
