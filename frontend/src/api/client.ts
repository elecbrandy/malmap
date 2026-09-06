export type ScoredEntry = {
  word: string;
  sense_no: number;
  definition: string;
  similarity: number;
  on_map: boolean;
  map_x: number | null;
  map_y: number | null;
};

type GuessResponse = {
  entries: ScoredEntry[];
};

type ApiErrorBody = {
  detail?: string;
};

/** 추측을 채점하고 각 sense의 결과를 돌려준다. */
export async function submitGuess(word: string): Promise<ScoredEntry[]> {
  const response = await fetch("/guess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ word }),
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new Error(body.detail ?? "추측을 채점하지 못했습니다. 잠시 후 다시 시도해 주세요.");
  }

  const data = (await response.json()) as GuessResponse;
  return data.entries;
}
