# AGENTS.md — 말맵(malmap)

이 저장소에서 작업하기 전에 항상 이 문서를 먼저 읽는다. 이 파일이 프로젝트 규칙의 단일 출처(single source of truth)다. `CLAUDE.md` 등 도구별 파일은 이 문서를 가리키는 포인터일 뿐이다.

## 이 프로젝트

의미 기반 한국어 단어 추리 게임. 꼬맨틀/Semantle의 게임성(정답과의 임베딩 유사도로 추리)에, 결과를 숫자 리스트가 아니라 **2차원 의미 지도**로 시각화하는 것이 핵심. 검색한 단어가 지도 위 타일로 나타나고 카메라가 그 위치로 이동한다.

기억할 것 세 가지:

1. **엔트리 단위는 "단어"가 아니라 "단어 + 뜻".** 동음이의어("밤"=night/chestnut)는 각각 별도 엔트리이고, 뜻풀이 문장을 임베딩해 지도상 다른 위치에 놓는다.
2. **지도에 있는 단어와 없는 단어가 구분된다.** 전체 사전(유사도 계산용, 수만 개) 중 일부만 지도 좌표를 갖는다(수백~1천여 개). 나머지는 점수만 매겨 스택에 표시.
3. **매일 정답이 바뀐다.** 지도 위 엔트리 중 하나가 그날의 정답.

## 기술 스택

- 백엔드: FastAPI (Python)
- 프론트엔드: React (TypeScript)
- DB: PostgreSQL + pgvector (개발: 로컬 도커 / 배포: Oracle Always Free VM에 직접 설치)
- 임베딩: 로컬 Hugging Face sentence-transformers. **라이선스 apache-2.0/mit 명시 모델만.** 사전에 없는 단어는 런타임 임베딩 후 캐싱.
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
- 파이프라인(파싱/필터/임베딩/좌표/적재) → `docs/rules/data-pipeline.md`
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

## 용어 사전 (코드/DB/API 전체 통일)

| 용어 | 의미 | 쓰지 말 것 |
|---|---|---|
| entry | 단어 + 뜻 조합, 기본 단위 | word, item |
| sense | 표제어 내 개별 뜻(의미 번호) | meaning |
| guess | 유저가 검색한 추측 | query, search |
| similarity | 코사인 유사도 (-1~1) | score, distance |
| on_map | 지도 좌표 보유 여부 | visible, placed |
| answer | 그날의 정답 엔트리 | target, solution |
| daily / play_date | 일일 라운드 / 게임 날짜 | round |

## 마일스톤

핵심 재미를 먼저 검증하고 시각화는 나중에 얹는다. 앞 단계를 건너뛰지 않는다.

- **M1**: 파이프라인 → DB 적재 (임베딩까지)
- **M2**: `/guess` API + curl 테스트
- **M3**: React 검색창 + 텍스트 결과만 (지도 없이) — **여기서 게임이 재밌는지 판단**
- **M4**: 지도 렌더링 + 카메라 이동
- **M5**: 지도 밖 스택 + 동음이의어 다중 타일
- **M6**: 일일 정답 로테이션 + 세션 기록
