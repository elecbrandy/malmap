"""한국어기초사전 entry의 뜻풀이를 임베딩하는 스크립트.

입력:  pipeline/output/entries_raw.jsonl
출력:  pipeline/output/entries_embedded.jsonl

모델: intfloat/multilingual-e5-base (MIT, 768차원)

실행:
    python pipeline/3_embed.py
    python pipeline/3_embed.py --batch-size 32 --device mps
"""

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

INPUT_FILE = Path("pipeline/output/entries_raw.jsonl")
OUTPUT_FILE = Path("pipeline/output/entries_embedded.jsonl")
MODEL_NAME = "intfloat/multilingual-e5-base"
EMBEDDING_DIMENSION = 768
DEFAULT_BATCH_SIZE = 64


def load_entries(input_file: Path) -> list[dict]:
    """JSONL 파일에서 임베딩할 entry를 읽는다.

    Args:
        input_file: 1_parse.py가 만든 entry JSONL 파일 경로.

    Returns:
        원본 필드를 보존한 entry 딕셔너리 목록.

    Raises:
        ValueError: 필수 필드가 없거나 형식이 올바르지 않은 경우.
    """
    entries: list[dict] = []

    with input_file.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            entry = json.loads(line)
            if not isinstance(entry, dict):
                raise ValueError(f"{line_number}번째 줄이 객체가 아닙니다.")

            word = entry.get("word")
            definition = entry.get("definition")
            if not isinstance(word, str) or not isinstance(definition, str):
                raise ValueError(f"{line_number}번째 줄에 word 또는 definition 문자열이 없습니다.")
            entries.append(entry)

    return entries


def build_embedding_text(entry: dict) -> str:
    """entry의 뜻풀이와 용례로 E5 입력 문장을 만든다.

    모든 sense에 반복되는 표제어는 제외하고, 실제 의미를 설명하는
    뜻풀이와 용례를 사용해 동음이의어의 문맥을 구분한다.

    Args:
        entry: word와 definition을 포함한 entry 딕셔너리.

    Returns:
        E5 모델에 전달할 접두사 포함 입력 문장. 용례가 없으면 뜻풀이만 포함한다.
    """
    embedding_text = f"query: {entry['definition']}"
    usage = entry.get("usage", "").strip()
    if usage:
        embedding_text += f" 예문: {usage}"
    return embedding_text


def parse_arguments() -> argparse.Namespace:
    """명령줄 인자를 읽는다."""
    parser = argparse.ArgumentParser(description="한국어 단어 뜻풀이 임베딩")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"한 번에 임베딩할 entry 수 (기본값: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--device",
        help="SentenceTransformer 실행 장치. 예: mps, cpu, cuda",
    )
    return parser.parse_args()


def main() -> None:
    """전체 entry를 배치 임베딩해 JSONL 파일로 저장한다."""
    arguments = parse_arguments()
    if arguments.batch_size < 1:
        raise ValueError("batch-size는 1 이상이어야 합니다.")
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {INPUT_FILE}")

    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as error:
        raise SystemExit(
            "sentence-transformers가 필요합니다. 현재 가상환경에 설치한 뒤 다시 실행하세요."
        ) from error

    entries = load_entries(INPUT_FILE)
    if not entries:
        raise ValueError(f"입력 파일에 entry가 없습니다: {INPUT_FILE}")

    # 모델 카드: MIT 라이선스, 768차원, 모든 입력에 query: 접두사 권장.
    model = SentenceTransformer(MODEL_NAME, device=arguments.device)
    embedding_dimension = model.get_sentence_embedding_dimension()
    if embedding_dimension != EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"임베딩 차원이 {embedding_dimension}입니다. "
            f"DB 스키마의 VECTOR({EMBEDDING_DIMENSION})와 일치하지 않습니다."
        )

    texts = [build_embedding_text(entry) for entry in entries]
    log.info("모델        : %s", MODEL_NAME)
    log.info("entry 수    : %d개", len(entries))
    log.info("배치 크기   : %d", arguments.batch_size)
    log.info("임베딩을 시작합니다.")

    embeddings = model.encode(
        texts,
        batch_size=arguments.batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = OUTPUT_FILE.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as file:
        for entry, embedding in zip(entries, embeddings, strict=True):
            file.write(
                json.dumps(
                    {**entry, "embedding": embedding.tolist()},
                    ensure_ascii=False,
                )
                + "\n"
            )
    temporary_file.replace(OUTPUT_FILE)

    log.info("출력 파일   : %s", OUTPUT_FILE)
    log.info("완료        : %d개 entry, %d차원", len(entries), embedding_dimension)


if __name__ == "__main__":
    main()
