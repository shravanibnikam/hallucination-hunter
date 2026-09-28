import { body, endpoint, json } from "@/lib/http";
import { idSchema, profileSchema } from "@/lib/schemas";
import { updateProfile } from "@/lib/game-service";
export async function PATCH(request:Request, context:{params:Promise<{id:string}>}) { return endpoint(async () => json(await updateProfile(idSchema.parse((await context.params).id), await body(request,profileSchema)))); }
