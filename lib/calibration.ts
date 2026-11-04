export interface CalibratedGuess {
  confidence: number;
  is_correct: boolean;
  is_attention_check: boolean;
}
/** Confidence 1 (pure guess) to 5 (certain) read as the probability of being right, 50% to 100%. */
export const statedProbability = (confidence: number) => 50 + (confidence - 1) * 12.5;
export function calibration(guesses: CalibratedGuess[]) {
  const items = guesses.filter(g => !g.is_attention_check);
  const byConfidence = [1, 2, 3, 4, 5].map(confidence => {
    const at = items.filter(g => g.confidence === confidence);
    return { confidence, correct: at.filter(g => g.is_correct).length, total: at.length };
  });
  if (!items.length)
    return { statedProbability: null, actualAccuracy: null, byConfidence, message: "There weren’t enough regular items to compare confidence this round." };
  const stated = items.reduce((sum, g) => sum + statedProbability(g.confidence), 0) / items.length;
  const actualAccuracy = items.filter(g => g.is_correct).length / items.length * 100;
  const difference = stated - actualAccuracy;
  const label = difference > 10 ? "overconfident" : difference < -10 ? "underconfident" : "well calibrated";
  return { statedProbability: stated, actualAccuracy, byConfidence, message: `You were ${label}: about ${Math.round(stated)}% sure on average, ${Math.round(actualAccuracy)}% correct.` };
}
export interface CategoryTotals {
  category: string;
  correct: number;
  total: number;
  players: number;
}
/** Other players' accuracy per category, withheld (null) until enough players make it an average rather than a person. */
export function playerAverages(rows: CategoryTotals[], minPlayers: number) {
  return new Map(rows.map(r => [r.category, r.players >= minPlayers && r.total ? r.correct / r.total * 100 : null]));
}
