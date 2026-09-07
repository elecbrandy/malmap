import { FormEvent, useRef, useState } from "react";

import { submitGuess, type ScoredEntry } from "./api/client";
import MapCanvas, { type CameraTarget } from "./MapCanvas";
import { formatScaledSimilarity } from "./similarity";
import "./App.css";

type GuessResult = {
  word: string;
  entries: ScoredEntry[];
};

function App() {
  const [guess, setGuess] = useState("");
  const [guessResults, setGuessResults] = useState<GuessResult[]>([]);
  const [cameraTarget, setCameraTarget] = useState<CameraTarget | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const resultReferences = useRef(new Map<string, HTMLLIElement>());
  const cameraRequestId = useRef(0);

  function moveCameraTo(entries: ScoredEntry[]) {
    const entry = entries.find(
      (candidate) => candidate.on_map && candidate.map_x !== null && candidate.map_y !== null,
    );
    if (!entry) return;

    cameraRequestId.current += 1;
    setCameraTarget({ entry, requestId: cameraRequestId.current });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const word = guess.trim();
    if (!word) {
      setErrorMessage("추측 단어를 입력해 주세요.");
      return;
    }

    const existingResult = guessResults.find((result) => result.word === word);
    if (existingResult) {
      moveCameraTo(existingResult.entries);
      resultReferences.current.get(word)?.scrollIntoView({ behavior: "smooth", block: "center" });
      setErrorMessage(null);
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const entries = await submitGuess(word);
      const sortedEntries = [...entries].sort(
        (firstEntry, secondEntry) => secondEntry.similarity - firstEntry.similarity,
      );
      const highestEntry = sortedEntries.slice(0, 1);
      moveCameraTo(highestEntry);
      setGuessResults((currentResults) =>
        [...currentResults, { word, entries: highestEntry }].sort(
          (firstResult, secondResult) =>
            (secondResult.entries[0]?.similarity ?? -1) -
            (firstResult.entries[0]?.similarity ?? -1),
        ),
      );
      setGuess("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "추측을 채점하지 못했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="game-shell">
      <header className="hero">
        <p className="eyebrow">오늘의 의미를 찾아서</p>
        <h1>말맵</h1>
        <p className="description">단어를 입력하면 정답과의 의미적 가까움을 알려드려요.</p>
      </header>

      <section className="guess-panel" aria-label="단어 추측">
        <form onSubmit={handleSubmit}>
          <label htmlFor="guess">추측 단어</label>
          <div className="input-row">
            <input
              id="guess"
              value={guess}
              onChange={(event) => setGuess(event.target.value)}
              placeholder="예: 바다"
              autoComplete="off"
              disabled={isSubmitting}
            />
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "채점 중…" : "추측"}
            </button>
          </div>
        </form>
        {errorMessage && <p className="error-message" role="alert">{errorMessage}</p>}
      </section>

      <section className="map-section" aria-label="의미 지도">
        <div className="section-heading">
          <h2>의미 지도</h2>
          <span>{guessResults.flatMap((result) => result.entries).filter((entry) => entry.on_map).length}개 발견</span>
        </div>
        <MapCanvas
          entries={guessResults.flatMap((result) => result.entries).filter((entry) => entry.on_map)}
          cameraTarget={cameraTarget}
        />
      </section>

      <section className="results" aria-live="polite" aria-label="추측 결과">
        <div className="results-heading">
          <h2>추측 기록</h2>
          <span>{guessResults.length}개 단어</span>
        </div>

        {guessResults.length === 0 ? (
          <p className="empty-state">첫 단어를 추측해 보세요. 가장 가까운 뜻부터 보여드려요.</p>
        ) : (
          <ol className="result-list">
            {guessResults.map(({ word, entries }) => {
              const [primaryEntry] = entries;
              if (!primaryEntry) return null;

              return (
                <li
                  className="guess-row"
                  key={word}
                  ref={(element) => {
                    if (element) resultReferences.current.set(word, element);
                  }}
                >
                  <div className="entry-main">
                    <div className="entry-word">
                      <h3>{primaryEntry.word}</h3>
                      <span className="sense">뜻 {primaryEntry.sense_no}</span>
                    </div>
                    <p>{primaryEntry.definition}</p>
                    <div className="entry-side">
                      <strong aria-label={`유사도 ${formatScaledSimilarity(primaryEntry.similarity)}`}>
                        {formatScaledSimilarity(primaryEntry.similarity)}
                      </strong>
                      <span className={primaryEntry.on_map ? "map-status on-map" : "map-status off-map"}>
                        {primaryEntry.on_map ? "지도" : "지도 밖"}
                      </span>
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </main>
  );
}

export default App;
