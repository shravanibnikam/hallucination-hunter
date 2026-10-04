import { rateLimit } from "@/lib/rate-limit";
import { body, endpoint, json } from "@/lib/http";
import { guessSchema } from "@/lib/schemas";
import { writeGuess } from "@/lib/game-service";
export async function POST(request: Request) {
  return endpoint(async () => {
    rateLimit("guesses", 600, 60000);
    const input = await body(request, guessSchema);
    rateLimit(`guesses:${input.sessionId}`, 30, 60000);
    return json(await writeGuess(input));

  });
}
