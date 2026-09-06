"""추측 채점 HTTP 엔드포인트와 M2 채점 흐름을 정의한다."""

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.app.core.database import get_connection
from backend.app.core.embedding import create_unknown_entry_embedding
from backend.app.schemas.guess import GuessRequest, GuessResponse, ScoredEntry

router = APIRouter(tags=["guess"])


@router.post("/guess", response_model=GuessResponse)
def guess(guess_request: GuessRequest, request: Request) -> GuessResponse:
    """추측 word의 모든 sense를 오늘 answer와 비교한다.

    Args:
        guess_request: 사용자가 보낸 원본 추측.
    Returns:
        각 sense를 독립적으로 채점한 결과 배열.
    """
    word = guess_request.word.strip()
    if not word:
        raise HTTPException(status_code=422, detail="추측 단어를 입력해 주세요.")

    entries = lookup_scored_entries(word)
    if not entries:
        cache_unknown_entry(word, request.app.state.embedding_model)
        entries = lookup_scored_entries(word)

    return GuessResponse(entries=[ScoredEntry.model_validate(entry) for entry in entries])


def lookup_scored_entries(word: str) -> list[dict[str, object]]:
    """word의 모든 entry를 오늘 answer 기준으로 SQL에서 채점한다.

    Args:
        word: 앞뒤 공백이 제거된 추측 표기.

    Returns:
        sense_no 순서의 entry별 similarity 결과.

    Raises:
        HTTPException: 오늘 answer가 아직 준비되지 않은 경우.
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    entry.word,
                    entry.sense_no,
                    entry.definition,
                    1 - (entry.embedding <=> answer.embedding) AS similarity,
                    entry.on_map,
                    entry.map_x,
                    entry.map_y
                FROM entries AS entry
                JOIN daily_answers AS daily_answer
                    ON daily_answer.play_date = %(play_date)s
                JOIN entries AS answer ON answer.id = daily_answer.entry_id
                WHERE entry.word = %(word)s
                ORDER BY entry.sense_no
                """,
                {"play_date": date.today(), "word": word},
            )
            entries = list(cursor.fetchall())

            if not entries:
                cursor.execute(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM daily_answers WHERE play_date = %(play_date)s
                    )
                    """,
                    {"play_date": date.today()},
                )
                answer_exists = cursor.fetchone()["exists"]
                if not answer_exists:
                    raise HTTPException(
                        status_code=503,
                        detail="오늘의 정답이 준비되지 않았습니다.",
                    )

    return entries


def cache_unknown_entry(word: str, embedding_model: Any) -> None:
    """사전에 없는 word를 E5로 임베딩해 지도 밖 entry로 upsert한다.

    Args:
        word: 사전에 없는, 공백 정리된 추측 표기.
        embedding_model: 앱 시작 시 한 번 로드한 E5 모델.
    """
    embedding = create_unknown_entry_embedding(embedding_model, word)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO entries (
                    word, sense_no, definition, pos, vocabulary_level, embedding, on_map
                )
                VALUES (
                    %(word)s, 0, %(definition)s, '미상', '없음', %(embedding)s::vector, FALSE
                )
                ON CONFLICT (word, sense_no) DO UPDATE SET
                    definition = EXCLUDED.definition,
                    pos = EXCLUDED.pos,
                    vocabulary_level = EXCLUDED.vocabulary_level,
                    embedding = EXCLUDED.embedding,
                    on_map = FALSE,
                    map_x = NULL,
                    map_y = NULL
                """,
                {
                    "word": word,
                    "definition": word,
                    "embedding": "[" + ",".join(str(value) for value in embedding) + "]",
                },
            )
