import { rateLimit } from "@/lib/rate-limit";
import { body, endpoint, json } from "@/lib/http";
import { sessionSchema } from "@/lib/schemas";
import { createSession } from "@/lib/game-service";
export async function POST(request: Request) {
  return endpoint(async () => {
    rateLimit("sessions", 60, 60000);
    return json(await createSession(await body(request, sessionSchema)), 201);

  });
}
