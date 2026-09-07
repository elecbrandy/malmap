"""전체 사전 entry의 UMAP 2차원 좌표를 생성하는 스크립트.

입력:  pipeline/output/entries_embedded.jsonl
출력:  pipeline/output/entries_with_coords.jsonl
       pipeline/output/map_scatter.png

실행:
    uv run python pipeline/4_project.py
"""

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

INPUT_FILE = Path("pipeline/output/entries_embedded.jsonl")
METADATA_FILE = Path("pipeline/output/entries_raw.jsonl")
OUTPUT_FILE = Path("pipeline/output/entries_with_coords.jsonl")
SCATTER_PLOT_FILE = Path("pipeline/output/map_scatter.png")
EMBEDDING_DIMENSION = 768
DEFAULT_RANDOM_SEED = 42


def parse_arguments() -> argparse.Namespace:
    """명령줄 인자를 읽는다."""
    parser = argparse.ArgumentParser(description="말맵용 2차원 의미 지도 생성")
    parser.add_argument(
        "--random-seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help=f"표본 선택과 UMAP 재현용 시드 (기본값: {DEFAULT_RANDOM_SEED})",
    )
    return parser.parse_args()


def read_entry(line: str, line_number: int) -> dict:
    """임베딩 JSONL 한 줄을 검증해 entry로 반환한다.

    Args:
        line: JSONL의 한 줄.
        line_number: 오류 메시지에 표시할 줄 번호.

    Returns:
        필수 필드가 검증된 entry 딕셔너리.

    Raises:
        ValueError: entry의 필수 필드나 임베딩 차원이 올바르지 않은 경우.
    """
    entry = json.loads(line)
    if not isinstance(entry, dict):
        raise ValueError(f"{line_number}번째 줄이 객체가 아닙니다.")

    word = entry.get("word")
    sense_no = entry.get("sense_no")
    embedding = entry.get("embedding")
    if not isinstance(word, str) or not isinstance(sense_no, int):
        raise ValueError(f"{line_number}번째 줄에 word 또는 sense_no가 없습니다.")
    if not isinstance(embedding, list) or len(embedding) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"{line_number}번째 줄의 embedding 차원이 {EMBEDDING_DIMENSION}이 아닙니다."
        )

    return entry


def load_vocabulary_levels(metadata_file: Path) -> dict[tuple[str, int], str]:
    """파싱 산출물에서 entry별 어휘 등급을 읽는다.

    현재 임베딩 산출물은 어휘 등급을 추가하기 전에 생성되었다. 임베딩을
    다시 계산하지 않고도 최신 메타데이터를 최종 산출물에 반영하기 위해
    raw 파일을 별도로 읽는다.

    Args:
        metadata_file: vocabulary_level을 포함한 raw JSONL 파일 경로.

    Returns:
        (word, sense_no)를 키로 하는 어휘 등급 사전.
    """
    vocabulary_levels: dict[tuple[str, int], str] = {}

    with metadata_file.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            entry = json.loads(line)
            word = entry.get("word")
            sense_no = entry.get("sense_no")
            vocabulary_level = entry.get("vocabulary_level")
            if not isinstance(word, str) or not isinstance(sense_no, int):
                raise ValueError(f"{line_number}번째 raw entry의 식별자가 올바르지 않습니다.")
            if not isinstance(vocabulary_level, str):
                raise ValueError(f"{line_number}번째 raw entry에 vocabulary_level이 없습니다.")
            vocabulary_levels[(word, sense_no)] = vocabulary_level

    return vocabulary_levels


def load_map_entries(
    input_file: Path,
    vocabulary_levels: dict[tuple[str, int], str],
) -> list[dict]:
    """전체 사전 entry를 지도 투영 대상으로 읽는다.

    Args:
        input_file: 임베딩 JSONL 파일 경로.
        vocabulary_levels: (word, sense_no)별 국립국어원 어휘 등급.

    Returns:
        지도에 투영할 전체 entry 목록.
    """
    entries: list[dict] = []

    with input_file.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            entry = read_entry(line, line_number)
            key = (entry["word"], entry["sense_no"])
            vocabulary_level = vocabulary_levels.get(key)
            if vocabulary_level is None:
                raise ValueError(f"{line_number}번째 임베딩 entry의 어휘 등급을 찾을 수 없습니다.")
            entry["vocabulary_level"] = vocabulary_level
            entries.append(entry)

    entries.sort(key=lambda entry: (entry["word"], entry["sense_no"]))
    return entries


def project_entries(entries: list[dict], random_seed: int) -> list[tuple[float, float]]:
    """선택한 entry 임베딩을 UMAP으로 2차원에 투영한다.

    Args:
        entries: embedding을 포함한 지도용 entry 목록.
        random_seed: UMAP 결과 재현용 시드.

    Returns:
        입력 entry 순서와 같은 2차원 좌표 목록.
    """
    import numpy
    import umap

    embeddings = numpy.asarray([entry["embedding"] for entry in entries], dtype=numpy.float32)
    mapper = umap.UMAP(
        n_components=2,
        n_neighbors=15,
        min_dist=0.25,
        metric="cosine",
        random_state=random_seed,
    )
    coordinates = mapper.fit_transform(embeddings)
    return [(float(x), float(y)) for x, y in coordinates]


def write_entries_with_coordinates(
    input_file: Path,
    output_file: Path,
    coordinates_by_entry: dict[tuple[str, int], tuple[float, float]],
    vocabulary_levels: dict[tuple[str, int], str],
) -> None:
    """전체 entry에 지도 여부와 좌표를 추가한 JSONL을 저장한다.

    Args:
        input_file: 임베딩 JSONL 파일 경로.
        output_file: 좌표 포함 JSONL 출력 경로.
        coordinates_by_entry: 지도 entry의 (word, sense_no)별 좌표.
        vocabulary_levels: (word, sense_no)별 국립국어원 어휘 등급.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = output_file.with_suffix(".tmp")

    with (
        input_file.open(encoding="utf-8") as input_handle,
        temporary_file.open("w", encoding="utf-8") as output_handle,
    ):
        for line_number, line in enumerate(input_handle, start=1):
            entry = read_entry(line, line_number)
            key = (entry["word"], entry["sense_no"])
            vocabulary_level = vocabulary_levels.get(key)
            if vocabulary_level is None:
                raise ValueError(f"{line_number}번째 임베딩 entry의 어휘 등급을 찾을 수 없습니다.")
            entry["vocabulary_level"] = vocabulary_level
            coordinates = coordinates_by_entry.get(key)
            if coordinates is None:
                entry.update(on_map=False, map_x=None, map_y=None)
            else:
                map_x, map_y = coordinates
                entry.update(on_map=True, map_x=map_x, map_y=map_y)
            output_handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    temporary_file.replace(output_file)


def save_scatter_plot(coordinates: list[tuple[float, float]], output_file: Path) -> None:
    """UMAP 결과를 빠르게 확인할 산포도 이미지를 저장한다.

    Args:
        coordinates: 지도 entry의 2차원 좌표 목록.
        output_file: PNG 출력 경로.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as pyplot

    x_coordinates, y_coordinates = zip(*coordinates, strict=True)
    figure, axis = pyplot.subplots(figsize=(10, 8))
    axis.scatter(x_coordinates, y_coordinates, s=8, alpha=0.6, linewidths=0)
    axis.set_title("Malmap UMAP Semantic Map")
    axis.set_xlabel("UMAP 1")
    axis.set_ylabel("UMAP 2")
    figure.tight_layout()
    figure.savefig(output_file, dpi=160)
    pyplot.close(figure)


def main() -> None:
    """전체 사전 entry의 좌표와 산포도를 생성한다."""
    arguments = parse_arguments()
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {INPUT_FILE}")
    if not METADATA_FILE.exists():
        raise FileNotFoundError(f"메타데이터 파일이 없습니다: {METADATA_FILE}")

    vocabulary_levels = load_vocabulary_levels(METADATA_FILE)
    map_entries = load_map_entries(INPUT_FILE, vocabulary_levels)
    if len(map_entries) < 2:
        raise ValueError("UMAP 투영에 필요한 후보 entry가 부족합니다.")

    log.info("지도 entry  : %d개", len(map_entries))
    log.info("UMAP 투영을 시작합니다.")
    coordinates = project_entries(map_entries, arguments.random_seed)
    coordinates_by_entry = {
        (entry["word"], entry["sense_no"]): coordinate
        for entry, coordinate in zip(map_entries, coordinates, strict=True)
    }

    write_entries_with_coordinates(
        INPUT_FILE,
        OUTPUT_FILE,
        coordinates_by_entry,
        vocabulary_levels,
    )
    save_scatter_plot(coordinates, SCATTER_PLOT_FILE)

    log.info("좌표 포함 파일: %s", OUTPUT_FILE)
    log.info("산포도 이미지 : %s", SCATTER_PLOT_FILE)


if __name__ == "__main__":
    main()
