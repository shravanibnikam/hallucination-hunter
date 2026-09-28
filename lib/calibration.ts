export interface CalibratedGuess { confidence: number; is_correct: boolean; is_attention_check: boolean }
export function calibration(guesses: CalibratedGuess[]) {
 const items = guesses.filter(g => !g.is_attention_check);
 if (!items.length) return { statedProbability: null, actualAccuracy: null, message:"There weren’t enough regular items to compare confidence this round." };
 const statedProbability = items.reduce((sum,g) => sum + 50 + (g.confidence - 1) * 12.5, 0) / items.length;
 const actualAccuracy = items.filter(g => g.is_correct).length / items.length * 100;
 const difference = statedProbability - actualAccuracy;
 const label = difference > 10 ? "overconfident" : difference < -10 ? "underconfident" : "well calibrated";
 return { statedProbability, actualAccuracy, message:`You were ${label}: about ${Math.round(statedProbability)}% sure on average, ${Math.round(actualAccuracy)}% correct.` };
}
