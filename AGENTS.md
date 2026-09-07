# AGENTS.md — 말맵(malmap)

이 저장소에서 작업하기 전에 항상 이 문서를 먼저 읽는다. 이 파일이 프로젝트 규칙의 단일 출처(single source of truth)다. `CLAUDE.md` 등 도구별 파일은 이 문서를 가리키는 포인터일 뿐이다.

## 이 프로젝트

의미 기반 한국어 단어 추리 게임. 꼬맨틀/Semantle의 게임성(정답과의 임베딩 유사도로 추리)에, 결과를 숫자 리스트가 아니라 **2차원 의미 지도**로 시각화하는 것이 핵심. 검색한 단어가 지도 위 타일로 나타나고 카메라가 그 위치로 이동한다.

기억할 것 세 가지:

1. **엔트리 단위는 "단어"가 아니라 "단어 + 뜻".** 동음이의어("밤"=night/chestnut)는 각각 별도 엔트리이고, 뜻풀이 문장을 임베딩해 지도상 다른 위치에 놓는다.
2. **전체 사전 entry가 지도 좌표를 갖는다.** 화면에는 발견한 entry만 표시하며, 사전에 없는 런타임 추측만 `on_map=false`로 스택에 표시한다.
3. **매일 정답이 바뀐다.** 지도 위 엔트리 중 하나를 entry 단위로 균등 무작위 선택한다.

## 기술 스택

- 백엔드: FastAPI (Python)
- 프론트엔드: React (TypeScript)
- DB: Supabase PostgreSQL + pgvector. 스키마는 Supabase SQL Editor에서 실행하고, 파이프라인은 `DATABASE_URL`로 연결한다. IPv6을 쓸 수 있으면 직접 연결을 우선하고, IPv4 환경에서는 session pooler를 쓴다.
- 임베딩: 로컬 Hugging Face `intfloat/multilingual-e5-base` (MIT, 768차원) + sentence-transformers. 모든 저장 entry는 `query: 표제어: 뜻풀이` 형식으로 L2 정규화해 임베딩한다. 사전에 없는 단어는 반드시 같은 모델로 런타임 임베딩 후 캐싱.
- 데이터: 국립국어원 (공공누리 라이선스 확인 후)

## 구조

```
malmap/
├── AGENTS.md           # 규칙의 단일 출처 (이 파일)
├── CLAUDE.md           # → AGENTS.md 포인터
├── _docs/rules/         # 영역별 상세 지침
├── pipeline/           # 데이터 전처리 + 임베딩 배치 (웹서버와 분리)
├── backend/            # FastAPI 앱
├── frontend/           # React 앱
└── schema.sql       # pgvector 스키마 (파이프라인과 백엔드가 공유)
```

작업 영역별로 해당 지침을 먼저 읽는다:
- 파이프라인(파싱/임베딩/좌표/적재) → `docs/rules/data-pipeline.md`
- 백엔드(라우터/채점/pgvector) → `docs/rules/backend.md`
- 프론트(지도/카메라/타일/상태) → `docs/rules/frontend.md`

## 전역 규칙

**오버엔지니어링 금지.** 소규모 프로젝트다. 지금 필요한 걸 필요한 만큼만. 같은 패턴이 3번 반복되기 전엔 추상화하지 않는다. 병목이 측정되기 전엔 캐시/큐 같은 인프라를 도입하지 않는다. "지금 지워서 안 깨지면 필요 없던 코드".

**언어답게 쓴다.** Python은 컴프리헨션·컨텍스트 매니저·pathlib·데이터클래스를 활용하고 Java식 습관을 피한다. JS/TS는 const(var 금지)·구조 분해·옵셔널 체이닝·async/await를 활용한다.

**코드 컨벤션**
- Python: `ruff` 포매팅/린팅. 함수 시그니처에 타입 힌트. **독스트링은 구글 스타일 + 한국어.** 주석은 한국어로, 왜(why)를 설명한다.
- JS/TS: `prettier` + `eslint`. TypeScript 기본, `any`는 최후의 수단. **주석/JSDoc은 한국어**, 왜를 설명한다.

```python
def score_guess(guess_vector: list[float], answer_vector: list[float]) -> float:
    """추측 단어와 정답 사이의 코사인 유사도를 계산한다.

    Args:
        guess_vector: 추측한 단어의 임베딩 벡터.
        answer_vector: 오늘의 정답 임베딩 벡터.

    Returns:
        -1.0 ~ 1.0 범위의 코사인 유사도. 값이 클수록 가깝다.
    """
```

**기타**
- 이름을 축약하지 않는다(관용적인 `id`/`db`/`x`/`y` 제외). 함수는 한 가지 일만.
- 에러를 조용히 삼키지 않는다(`except: pass`, 빈 `catch {}` 금지). 사용자용 메시지는 한국어.
- 한 번에 한 가지만 바꾼다. 요청 안 한 파일을 "김에" 고치지 않는다.

## M1 파이프라인과 DB

현재 M1은 별도 필터 단계 없이 파서의 최소 검증만 사용한다. 파서가 명사가 아닌 entry, 의존 명사 목록, 빈 뜻풀이, 중복 `(word, definition)`을 제거하고 표제어별 `sense_no`를 다시 부여하므로 `2_filter.py`는 만들지 않는다.

```text
국립국어원 JSON
  → 1_parse.py → entries_raw.jsonl
  → 3_embed.py → entries_embedded.jsonl
  → 4_project.py → entries_with_coords.jsonl + map_scatter.png
  → 5_load.py → Supabase entries
```

- `vocabulary_level`은 국립국어원 원본의 `초급`/`중급`/`고급`/`없음` 값을 raw JSONL에 기록하고, 이후 임베딩·좌표 단계는 이 메타데이터를 보존한다.
- 전체 사전 entry에 고정 지도 좌표를 부여한다. 사전에 없는 런타임 추측만 `on_map=false`로 캐싱한다.
- UMAP은 전체 사전 벡터에 `metric="cosine"`, 고정 `random_state`로 실행한다. 2D 좌표는 이웃 힌트일 뿐이고, 정답과의 정확한 관계는 원래 768차원 공간의 similarity가 담당한다. 지도 좌표를 매일 다시 만들지 않는다.
- `5_load.py`는 `entries_with_coords.jsonl`을 임시 staging 테이블에 `COPY`로 적재한 뒤 `(word, sense_no)` 기준으로 upsert한다. M1의 `/guess`는 word 조회 후 소수 entry만 answer와 비교하므로 ivfflat 인덱스를 만들지 않는다. 전체 벡터 최근접 검색이 측정된 병목일 때만 적재 후 추가한다.
- Supabase 연결 문자열은 `DATABASE_URL` 환경 변수로만 전달한다. 코드·Git·공유 문서에 비밀값을 넣지 않는다.

## 용어 사전 (코드/DB/API 전체 통일)

| 용어 | 의미 | 쓰지 말 것 |
|---|---|---|
| entry | 단어 + 뜻 조합, 기본 단위 | word, item |
| sense | 표제어 내 개별 뜻(의미 번호) | meaning |
| guess | 유저가 검색한 추측 | query, search |
| similarity | 코사인 유사도 (-1~1) | score, distance |
| on_map | 지도 좌표 보유 여부 | visible, placed |
| vocabulary_level | 국립국어원 어휘 등급 | level, difficulty |
| answer | 그날의 정답 엔트리 | target, solution |
| daily / play_date | 일일 라운드 / 게임 날짜 | round |

## 마일스톤

핵심 재미를 먼저 검증하고 시각화는 나중에 얹는다. 앞 단계를 건너뛰지 않는다.

- **M1**: 파이프라인 → DB 적재 (임베딩까지) — 완료
- **M2**: `/guess` API + curl 테스트 — 완료
  - FastAPI `/guess`는 모든 sense를 pgvector SQL로 채점하고, 사전 밖 추측은 동일한 E5 모델로 임베딩해 `on_map=false` entry로 캐싱한다.
  - 백엔드는 `api/guess.py`에 채점 흐름을 두고, 공용 DB 연결·임베딩·요청/응답 스키마만 별도 모듈로 둔다.
  - 사전 단어·동음이의어·사전 밖 단어의 curl 검증과 API 단위 테스트를 마쳤다.
- **M3**: React 검색창 + 텍스트 결과만 (지도 없이) — **여기서 게임이 재밌는지 판단**
- **M4**: 지도 렌더링 + 카메라 이동
- **M5**: 지도 밖 스택 + 동음이의어 다중 타일
- **M6**: 일일 정답 로테이션 + 세션 기록
