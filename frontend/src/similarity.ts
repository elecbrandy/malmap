const MINIMUM_SIMILARITY = 0.7;
const MAXIMUM_SIMILARITY = 1;

/** 원시 similarity를 0.00~100.00 범위의 표시값으로 변환한다. */
export function formatScaledSimilarity(similarity: number): string {
  const scaledSimilarity =
    ((similarity - MINIMUM_SIMILARITY) / (MAXIMUM_SIMILARITY - MINIMUM_SIMILARITY)) * 100;
  return Math.min(100, Math.max(0, scaledSimilarity)).toFixed(2);
}
