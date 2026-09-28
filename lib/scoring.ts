import type { Side } from "./types";
/** Correctness is derived only from the server-stored layout, never a client score. */
export function isCorrect(fakeShownOn: Side, chosenSide: Side): boolean { return fakeShownOn === chosenSide; }
export function scoreGuesses(guesses: { is_correct: boolean }[]) {
 let score = 0, currentStreak = 0, bestStreak = 0;
 for (const guess of guesses) { if (guess.is_correct) { score++; currentStreak++; bestStreak = Math.max(bestStreak, currentStreak); } else currentStreak = 0; }
 return { score, currentStreak, bestStreak };
}
