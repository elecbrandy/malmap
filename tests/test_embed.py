"""임베딩 입력 문장 구성을 검증한다."""

import runpy
from typing import Callable

build_embedding_text: Callable[[dict], str] = runpy.run_path("pipeline/3_embed.py")[
    "build_embedding_text"
]


def test_build_embedding_text_uses_definition_and_usage() -> None:
    """표제어를 제외하고 뜻풀이와 용례를 입력에 포함한다."""
    entry = {
        "word": "눈",
        "definition": "태풍에서 중심을 이루는 부분.",
        "usage": "태풍의 눈에 속하는 지역은 날씨가 맑다.",
    }

    assert build_embedding_text(entry) == (
        "query: 태풍에서 중심을 이루는 부분. 예문: 태풍의 눈에 속하는 지역은 날씨가 맑다."
    )


def test_build_embedding_text_omits_empty_usage() -> None:
    """용례가 없으면 뜻풀이만 입력에 포함한다."""
    entry = {"word": "밤", "definition": "해가 진 뒤의 어두운 동안.", "usage": ""}

    assert build_embedding_text(entry) == "query: 해가 진 뒤의 어두운 동안."
