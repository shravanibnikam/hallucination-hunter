import type { Condition, Judgment, Side } from "./types";
/** Derive correctness from the assigned condition and stored layout only. */
export function isCorrect(condition: Condition, layout: { fake_shown_on: Side | null; shown_answer: "real" | "fake" | null }, choice: { chosenSide?: Side; judgment?: Judgment }): boolean {
 if (condition === "paired") return choice.chosenSide !== undefined && choice.chosenSide === layout.fake_shown_on;
 return (choice.judgment === "yes" && layout.shown_answer === "fake") || (choice.judgment === "no" && layout.shown_answer === "real");
}
export function scoreGuesses(guesses: { is_correct: boolean }[]) {
 let score = 0, currentStreak = 0, bestStreak = 0;
 for (const guess of guesses) {
  if (guess.is_correct) { score++; currentStreak++; bestStreak = Math.max(bestStreak, currentStreak); }
  else currentStreak = 0;
 }
 return { score, currentStreak, bestStreak };
}
