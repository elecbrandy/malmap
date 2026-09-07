"""국립국어원 entry 중복 제거와 sense 번호 부여를 검증한다."""

import runpy
from typing import Callable

deduplicate_and_renumber_entries: Callable[[list[dict]], list[dict]] = runpy.run_path(
    "pipeline/1_parse.py"
)["deduplicate_and_renumber_entries"]


def test_preserves_homonyms_and_renumbers_senses() -> None:
    """기존 sense 번호가 같아도 뜻풀이가 다르면 모두 보존한다."""
    entries = [
        {"word": "밤", "sense_no": 1, "definition": "해가 진 뒤의 어두운 동안."},
        {"word": "밤", "sense_no": 1, "definition": "밤나무의 열매."},
        {"word": "배", "sense_no": 3, "definition": "사람이나 동물의 복부."},
    ]

    result = deduplicate_and_renumber_entries(entries)

    assert [(entry["word"], entry["sense_no"]) for entry in result] == [
        ("밤", 1),
        ("밤", 2),
        ("배", 1),
    ]


def test_removes_only_identical_word_and_definition() -> None:
    """표제어와 뜻풀이가 모두 같은 entry만 중복 제거한다."""
    entries = [
        {"word": "눈", "sense_no": 1, "definition": "물체를 보는 감각 기관."},
        {"word": "눈", "sense_no": 4, "definition": "물체를 보는 감각 기관."},
    ]

    result = deduplicate_and_renumber_entries(entries)

    assert len(result) == 1
    assert result[0]["sense_no"] == 1
