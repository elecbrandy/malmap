-- 말맵(malmap) DB 스키마
-- 대상: PostgreSQL + pgvector (Supabase에서 그대로 실행 가능)
--
-- 사용법:
--   Supabase 대시보드 → SQL Editor에 이 파일을 붙여넣고 실행.
--   또는: psql "<커넥션 문자열>" -f db/schema.sql
--
-- 주의: 이 파일은 파이프라인(5_load.py)과 백엔드가 공유하는 단일 스키마 출처다.
--       용어는 AGENTS.md 용어 사전을 따른다(entry/sense/similarity/on_map/answer).


-- ── 확장 ────────────────────────────────────────────────
-- 벡터 유사도 검색을 위한 pgvector. Supabase는 미리 제공하므로 켜기만 하면 된다.
CREATE EXTENSION IF NOT EXISTS vector;


-- ── entries: 게임의 기본 단위 (단어 + 뜻) ─────────────────
-- 동음이의어는 같은 word에 서로 다른 sense_no를 가진 별개 행으로 저장한다.
-- 예: ('밤', 1, '해가 진 뒤...'), ('밤', 2, '밤나무의 열매')
-- 임베딩은 표제어가 아니라 뜻풀이(definition)를 벡터화한 값이다.
CREATE TABLE entries (
    id          SERIAL PRIMARY KEY,
    word        TEXT      NOT NULL,           -- 표기 (예: "밤")
    sense_no    INT       NOT NULL,           -- 표제어 내 의미 번호 (1, 2, ...)
    definition  TEXT      NOT NULL,           -- 뜻풀이 전문
    pos         TEXT      NOT NULL,           -- 품사 (명사로 필터링되어 들어옴)
    frequency   INT,                          -- 사용 빈도 (필터링/정렬용, 없으면 NULL)

    -- 임베딩 차원(768)은 사용하는 모델에 종속된다.
    -- 모델을 바꾸면 이 숫자와 파이프라인/백엔드의 차원 설정을 함께 바꿔야 한다.
    embedding   VECTOR(768) NOT NULL,

    -- 지도 배치 정보. on_map=true인 엔트리만 좌표를 가진다.
    -- 나머지(대다수)는 유사도 계산에만 쓰이고 지도에는 표시되지 않는다.
    on_map      BOOLEAN   NOT NULL DEFAULT FALSE,
    map_x       REAL,                         -- UMAP 2D x좌표 (on_map=true일 때만)
    map_y       REAL,                         -- UMAP 2D y좌표

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 같은 (표기, 의미번호) 조합은 유일하다. 파이프라인 재적재 시 upsert 기준이 된다.
CREATE UNIQUE INDEX entries_word_sense_idx ON entries (word, sense_no);

-- 검색어로 들어온 word의 모든 sense를 빠르게 조회하기 위한 인덱스.
CREATE INDEX entries_word_idx ON entries (word);

-- 지도 데이터(GET /map)를 빠르게 뽑기 위한 부분 인덱스.
CREATE INDEX entries_on_map_idx ON entries (on_map) WHERE on_map = TRUE;

-- 벡터 유사도 검색용 ivfflat 인덱스 (코사인 거리).
-- 주의: ivfflat은 데이터가 어느 정도 적재된 뒤 생성해야 품질이 좋다.
--       파이프라인에서 대량 적재를 끝낸 뒤 이 인덱스를 만드는 것을 권장한다.
--       (여기서는 스키마 정의를 한곳에 두기 위해 함께 선언하되,
--        대량 적재 전이라면 5_load.py에서 재생성하는 방식도 가능하다.)
CREATE INDEX entries_embedding_idx ON entries
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);


-- ── daily_answers: 그날의 정답 ───────────────────────────
-- 하루에 하나의 엔트리가 정답이 된다. 정답은 on_map=true인 엔트리 중에서 고른다.
CREATE TABLE daily_answers (
    id         SERIAL PRIMARY KEY,
    play_date  DATE      NOT NULL UNIQUE,      -- 게임 날짜 (하루 1개)
    entry_id   INT       NOT NULL REFERENCES entries(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ── answer_ranks: 정답 기준 사전 계산된 순위 (선택적) ──────
-- "정답과 가까운 순서 몇 위"를 보여주려면, 매 요청마다 전체 정렬하는 대신
-- 일일 정답이 정해질 때 배치로 순위를 계산해 저장해둔다.
-- 순위 기능을 M6 이후로 미룬다면 이 테이블은 나중에 만들어도 된다.
CREATE TABLE answer_ranks (
    play_date  DATE      NOT NULL REFERENCES daily_answers(play_date),
    entry_id   INT       NOT NULL REFERENCES entries(id),
    rank       INT       NOT NULL,             -- 1위 = 정답 자신, 클수록 멂
    similarity REAL      NOT NULL,             -- 그때 계산한 코사인 유사도
    PRIMARY KEY (play_date, entry_id)
);


-- ── guess_logs: 익명 세션의 추측 기록 ────────────────────
-- 로그인 없이 클라이언트가 발급한 세션 UUID로 구분한다.
-- 지금은 기록만 남긴다. 통계/공유 기능은 이후 마일스톤에서 이 데이터를 활용한다.
CREATE TABLE guess_logs (
    id          SERIAL PRIMARY KEY,
    session_id  UUID      NOT NULL,            -- 클라이언트가 발급한 익명 세션 식별자
    play_date   DATE      NOT NULL,            -- 어떤 날짜의 게임에 대한 추측인지
    entry_id    INT       REFERENCES entries(id),  -- 사전에 있던 단어면 참조, 없으면 NULL
    guess_text  TEXT      NOT NULL,            -- 실제 입력한 문자열 (사전에 없던 단어 추적용)
    similarity  REAL      NOT NULL,            -- 그 추측의 유사도
    guessed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 한 세션이 그날 어떤 추측들을 했는지 되짚기 위한 인덱스.
CREATE INDEX guess_logs_session_date_idx ON guess_logs (session_id, play_date);