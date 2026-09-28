import { body, endpoint, json } from "@/lib/http";
import { guessSchema } from "@/lib/schemas";
import { writeGuess } from "@/lib/game-service";
export async function POST(request: Request) { return endpoint(async () => json(await writeGuess(await body(request,guessSchema)))); }
