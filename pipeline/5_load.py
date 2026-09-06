"""좌표와 임베딩을 Supabase PostgreSQL에 적재하는 스크립트.

입력:  pipeline/output/entries_with_coords.jsonl
출력:  PostgreSQL entries 테이블

실행 전:
    1. Supabase SQL Editor에서 schema.sql을 실행한다.
    2. DATABASE_URL에 Supabase 직접 연결 문자열(IPv4 환경에서는 session pooler)을 설정한다.

실행:
    uv run python pipeline/5_load.py
"""

import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

INPUT_FILE = Path("pipeline/output/entries_with_coords.jsonl")
EMBEDDING_DIMENSION = 768
COPY_COLUMNS = (
    "word",
    "sense_no",
    "definition",
    "pos",
    "vocabulary_level",
    "embedding",
    "on_map",
    "map_x",
    "map_y",
)


def serialize_embedding(embedding: list[float]) -> str:
    """JSON 숫자 배열을 pgvector 입력 문자열로 변환한다.

    Args:
        embedding: 768차원 임베딩 숫자 배열.

    Returns:
        pgvector가 해석할 수 있는 대괄호 형식의 벡터 문자열.

    Raises:
        ValueError: 벡터 차원이 스키마와 다를 경우.
    """
    if len(embedding) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"임베딩 차원이 {len(embedding)}입니다. "
            f"VECTOR({EMBEDDING_DIMENSION})와 일치하지 않습니다."
        )
    return "[" + ",".join(str(value) for value in embedding) + "]"


def iter_rows(input_file: Path) -> Iterator[tuple[object, ...]]:
    """좌표 포함 JSONL을 Supabase COPY용 행으로 변환한다.

    Args:
        input_file: 4_project.py가 만든 JSONL 파일 경로.

    Yields:
        entries_staging 테이블 열 순서에 맞는 행.

    Raises:
        ValueError: entry의 필수 필드가 없거나 형식이 올바르지 않은 경우.
    """
    with input_file.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            entry = json.loads(line)
            required_fields = (
                "word",
                "sense_no",
                "definition",
                "pos",
                "vocabulary_level",
                "embedding",
                "on_map",
            )
            missing_fields = [field for field in required_fields if field not in entry]
            if missing_fields:
                fields = ", ".join(missing_fields)
                raise ValueError(f"{line_number}번째 entry에 필수 필드가 없습니다: {fields}")

            embedding = entry["embedding"]
            if not isinstance(embedding, list):
                raise ValueError(f"{line_number}번째 entry의 embedding이 배열이 아닙니다.")

            yield (
                entry["word"],
                entry["sense_no"],
                entry["definition"],
                entry["pos"],
                entry["vocabulary_level"],
                serialize_embedding(embedding),
                entry["on_map"],
                entry.get("map_x"),
                entry.get("map_y"),
            )


def create_staging_table(cursor: object) -> None:
    """현재 연결에서만 쓸 임시 적재 테이블을 만든다.

    Args:
        cursor: psycopg 데이터베이스 커서.
    """
    cursor.execute(
        """
        CREATE TEMP TABLE entries_staging (
            word TEXT NOT NULL,
            sense_no INT NOT NULL,
            definition TEXT NOT NULL,
            pos TEXT NOT NULL,
            vocabulary_level TEXT NOT NULL,
            embedding VECTOR(768) NOT NULL,
            on_map BOOLEAN NOT NULL,
            map_x REAL,
            map_y REAL
        ) ON COMMIT DROP
        """
    )


def copy_entries(cursor: object, input_file: Path) -> int:
    """JSONL entry를 임시 테이블에 COPY로 일괄 적재한다.

    Args:
        cursor: psycopg 데이터베이스 커서.
        input_file: 좌표 포함 JSONL 파일 경로.

    Returns:
        임시 테이블에 쓴 entry 수.
    """
    copy_statement = f"COPY entries_staging ({', '.join(COPY_COLUMNS)}) FROM STDIN"
    entry_count = 0
    with cursor.copy(copy_statement) as copy:
        for row in iter_rows(input_file):
            copy.write_row(row)
            entry_count += 1
    return entry_count


def upsert_entries(cursor: object) -> None:
    """임시 테이블의 entry를 기본 테이블에 반영한다.

    Args:
        cursor: psycopg 데이터베이스 커서.
    """
    cursor.execute(
        """
        INSERT INTO entries (
            word, sense_no, definition, pos, vocabulary_level,
            embedding, on_map, map_x, map_y
        )
        SELECT
            word, sense_no, definition, pos, vocabulary_level,
            embedding, on_map, map_x, map_y
        FROM entries_staging
        ON CONFLICT (word, sense_no) DO UPDATE SET
            definition = EXCLUDED.definition,
            pos = EXCLUDED.pos,
            vocabulary_level = EXCLUDED.vocabulary_level,
            embedding = EXCLUDED.embedding,
            on_map = EXCLUDED.on_map,
            map_x = EXCLUDED.map_x,
            map_y = EXCLUDED.map_y
        """
    )


def get_entry_counts(cursor: object) -> tuple[int, int]:
    """적재 후 전체 entry와 지도 entry 수를 조회한다.

    Args:
        cursor: psycopg 데이터베이스 커서.

    Returns:
        전체 entry 수와 on_map=true entry 수.
    """
    cursor.execute(
        "SELECT count(*), count(*) FILTER (WHERE on_map) FROM entries"
    )
    entry_count, map_entry_count = cursor.fetchone()
    return entry_count, map_entry_count


def main() -> None:
    """Supabase에 전체 entry를 idempotent하게 적재한다."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL 환경 변수가 필요합니다.")
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {INPUT_FILE}")

    try:
        import psycopg
    except ModuleNotFoundError as error:
        raise SystemExit("psycopg가 필요합니다. uv sync 후 다시 실행하세요.") from error

    log.info("입력 파일   : %s", INPUT_FILE)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            create_staging_table(cursor)
            copied_entry_count = copy_entries(cursor, INPUT_FILE)
            log.info("임시 적재   : %d개 entry", copied_entry_count)

            upsert_entries(cursor)
            total_entry_count, map_entry_count = get_entry_counts(cursor)

    log.info("DB 전체 entry: %d개", total_entry_count)
    log.info("DB 지도 entry: %d개", map_entry_count)
    log.info("Supabase 적재가 완료되었습니다.")


if __name__ == "__main__":
    main()
