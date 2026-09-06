"""한국어기초사전 JSON 파싱 스크립트.

입력:  data/krdict/*.json  (국립국어원 한국어기초사전 전체 파일 11개)
출력:  pipeline/output/entries_raw.jsonl  (명사 엔트리, 한 줄 = 한 entry)

출력 필드:
    word        (str)  표기
    sense_no    (int)  의미 번호 (1부터 시작)
    definition  (str)  한국어 뜻풀이
    pos         (str)  품사 (이 단계에서는 "명사"만 통과)
    vocabulary_level (str) 국립국어원 어휘 등급 (초급/중급/고급/없음)
    usage       (str)  예문 첫 번째 문장형 예시. 없으면 빈 문자열.

실행:
    python pipeline/1_parse.py
"""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# ── 경로 설정 ────────────────────────────────────────────
DATA_DIR = Path("_data/korean")
OUTPUT_DIR = Path("pipeline/output")
OUTPUT_FILE = OUTPUT_DIR / "entries_raw.jsonl"

# 이 품사만 통과. 의존명사는 별도 필터링하지 않아도 기초사전엔 거의 없음.
ALLOWED_POS = {"명사"}

# 의존명사처럼 게임에 부적합한 단어 목록 (표기 기준)
EXCLUDE_WORDS = {"것", "수", "바", "데", "때", "만큼", "뿐", "채", "척", "체"}


def _to_list(value: dict | list) -> list:
    """단일 딕셔너리이거나 리스트인 필드를 항상 리스트로 반환한다.

    국립국어원 JSON은 항목이 하나면 dict, 여럿이면 list로 오는
    일관성 없는 구조를 가진다. 이 함수로 통일한다.
    """
    if isinstance(value, list):
        return value
    return [value]


def _get_feat_val(feats: dict | list, att: str) -> str | None:
    """feat 배열(또는 단일 feat)에서 특정 att의 val을 반환한다.

    Args:
        feats: 단일 feat 딕셔너리 또는 feat 딕셔너리의 리스트.
        att: 찾을 attribute 이름.

    Returns:
        해당 att의 val 문자열. 없으면 None.
    """
    for feat in _to_list(feats):
        if feat.get("att") == att:
            return feat.get("val")
    return None


def _extract_usage(sense_examples: list) -> str:
    """SenseExample 목록에서 '문장' 타입 예문을 추출한다.

    '문장' 타입이 없으면 '구' 타입 중 첫 번째를 반환한다.
    임베딩 보강용이라 하나면 충분하다.

    Args:
        sense_examples: SenseExample 딕셔너리 리스트.

    Returns:
        예문 문자열. 없으면 빈 문자열.
    """
    phrase_fallback = ""

    for example_item in sense_examples:
        feats = _to_list(example_item.get("feat", []))
        example_type = _get_feat_val(feats, "type")
        example_text = _get_feat_val(feats, "example")

        if not example_text:
            continue
        if example_type == "문장":
            return example_text
        if example_type == "구" and not phrase_fallback:
            phrase_fallback = example_text

    return phrase_fallback


def _extract_word(lemma: dict | list) -> str:
    """Lemma 구조에서 대표 표기(writtenForm)를 추출한다.

    한국어기초사전은 표제어가 하나면 딕셔너리, 이형태가 함께 있으면
    리스트로 제공한다. 대표 표기만 게임의 entry 표기로 사용한다.

    Args:
        lemma: 단일 Lemma 딕셔너리 또는 Lemma 딕셔너리의 리스트.

    Returns:
        대표 표기. writtenForm이 없으면 빈 문자열.
    """
    for lemma_item in _to_list(lemma):
        word = _get_feat_val(lemma_item.get("feat", {}), "writtenForm")
        if word:
            return word.strip()
    return ""


def _parse_entry(entry: dict) -> list[dict]:
    """LexicalEntry 하나를 파싱해 entry 딕셔너리 리스트로 반환한다.

    동음이의어 뜻풀이 수만큼 여러 entry가 나올 수 있다.
    명사가 아니거나 제외 단어면 빈 리스트를 반환한다.

    Args:
        entry: LexicalEntry 딕셔너리.

    Returns:
        파싱된 entry 딕셔너리 리스트.
    """
    # 품사 확인 (LexicalEntry 레벨 feat에 있음)
    entry_feats = entry.get("feat", [])
    pos = _get_feat_val(entry_feats, "partOfSpeech")
    if pos not in ALLOWED_POS:
        return []
    vocabulary_level = _get_feat_val(entry_feats, "vocabularyLevel") or "없음"

    # 표기
    word = _extract_word(entry.get("Lemma", {}))
    if not word or word in EXCLUDE_WORDS:
        return []

    # Sense는 하나면 dict, 여럿이면 list로 옴
    senses = _to_list(entry.get("Sense", []))

    results = []
    for sense in senses:
        # sense_no: val 필드가 "1", "2" 등 문자열로 옴
        sense_no_raw = sense.get("val")
        try:
            sense_no = int(sense_no_raw)
        except (TypeError, ValueError):
            # val이 없거나 파싱 불가면 순서로 대체
            sense_no = len(results) + 1

        # 뜻풀이: feat이 단일이거나 리스트
        sense_feats = sense.get("feat", {})
        definition = _get_feat_val(sense_feats, "definition") or ""
        definition = definition.strip()
        if not definition:
            continue

        # 예문 (임베딩 보강용, DB에는 저장 안 함)
        sense_examples = _to_list(sense.get("SenseExample", []))
        usage = _extract_usage(sense_examples)

        results.append({
            "word": word,
            "sense_no": sense_no,
            "definition": definition,
            "pos": pos,
            "vocabulary_level": vocabulary_level,
            "usage": usage,
        })

    return results


def parse_file(json_path: Path) -> list[dict]:
    """JSON 파일 하나를 파싱해 entry 리스트를 반환한다.

    Args:
        json_path: 파싱할 JSON 파일 경로.

    Returns:
        파싱된 entry 딕셔너리 리스트.
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    lexical_entries = _to_list(
        data.get("LexicalResource", {})
            .get("Lexicon", {})
            .get("LexicalEntry", [])
    )

    results = []
    for entry in lexical_entries:
        results.extend(_parse_entry(entry))
    return results


def main() -> None:
    """전체 파일을 파싱해 JSONL로 저장한다."""
    if not DATA_DIR.exists():
        log.error("데이터 디렉토리가 없습니다: %s", DATA_DIR)
        log.error("국립국어원 한국어기초사전 파일을 data/krdict/ 에 넣어주세요.")
        return

    json_files = sorted(DATA_DIR.glob("*.json"))
    if not json_files:
        log.error("JSON 파일이 없습니다: %s", DATA_DIR)
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_entries = 0
    total_raw = 0

    all_entries: list[dict] = []
    for json_path in json_files:
        entries = parse_file(json_path)
        all_entries.extend(entries)
        log.info("  %s → %d개 명사 entry", json_path.name, len(entries))

    # (word, sense_no) 중복 제거 — 파일 간 중복이 있을 경우 대비
    seen: set[tuple[str, int]] = set()
    unique_entries: list[dict] = []
    for entry in all_entries:
        key = (entry["word"], entry["sense_no"])
        if key not in seen:
            seen.add(key)
            unique_entries.append(entry)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for entry in unique_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    log.info("─" * 40)
    log.info("파일 수     : %d개", len(json_files))
    log.info("총 entry 수 : %d개", len(unique_entries))
    log.info("출력 파일   : %s", OUTPUT_FILE)


if __name__ == "__main__":
    main()
