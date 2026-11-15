import type { PredictionItem } from '@/types/clinical'

/**
 * Model scores are threshold-normalized (TorchXRayVision operating points):
 * 0.50 is the model's decision threshold. They are NOT calibrated probabilities,
 * so they must never be displayed as a "% chance" of disease.
 */
export const SCORE_THRESHOLD = 0.5

/** Scores this close to the threshold flip easily (cropping, compression, annotations). */
export const BORDERLINE_MARGIN = 0.1

export const SCORE_EXPLANATION =
  'Score 0.50 is the model’s decision threshold (≥ 0.50 = positive). It is not a percentage chance of disease; scores between 0.40 and 0.60 are borderline.'

export type ScoreVerdict = 'Positive' | 'Negative'

export function isPositive(pred: Pick<PredictionItem, 'probability' | 'is_positive'>): boolean {
  return pred.is_positive ?? pred.probability >= SCORE_THRESHOLD
}

export function scoreVerdict(pred: Pick<PredictionItem, 'probability' | 'is_positive'>): ScoreVerdict {
  return isPositive(pred) ? 'Positive' : 'Negative'
}

export function isBorderline(score: number): boolean {
  return Math.abs(score - SCORE_THRESHOLD) < BORDERLINE_MARGIN
}

export function formatScore(score: number): string {
  return score.toFixed(2)
}

/** e.g. "Negative · 0.34" or "Positive · 0.52 · borderline" */
export function describeScore(pred: Pick<PredictionItem, 'probability' | 'is_positive'>): string {
  const parts = [scoreVerdict(pred), formatScore(pred.probability)]
  if (isBorderline(pred.probability)) parts.push('borderline')
  return parts.join(' · ')
}

/** Predictions sorted by score, highest first (the API returns them in a fixed pathology order). */
export function rankPredictions(predictions: PredictionItem[]): PredictionItem[] {
  return [...predictions].sort((a, b) => b.probability - a.probability)
}
