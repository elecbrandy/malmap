import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture(autouse=True)
def stub_embedding_model(monkeypatch) -> None:
    """API 단위 테스트에서 무거운 E5 모델 로드를 피한다."""
    monkeypatch.setattr("backend.app.main.load_embedding_model", lambda: object())


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    """테스트 간 FastAPI 의존성 대체가 남지 않게 한다."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_guess_trims_word_and_returns_each_sense(monkeypatch) -> None:
    """앞뒤 공백을 제거하고 동음이의어를 각각 반환한다."""
    received_words: list[str] = []

    def fake_lookup(word: str) -> list[dict[str, object]]:
        received_words.append(word)
        return [
            {
                "word": "밤",
                "sense_no": 1,
                "definition": "해가 진 뒤부터 날이 밝기 전까지의 동안.",
                "similarity": 0.12,
                "on_map": True,
                "map_x": 1.5,
                "map_y": -2.0,
            },
            {
                "word": "밤",
                "sense_no": 2,
                "definition": "밤나무의 열매.",
                "similarity": 0.41,
                "on_map": False,
                "map_x": None,
                "map_y": None,
            },
        ]

    monkeypatch.setattr("backend.app.api.guess.lookup_scored_entries", fake_lookup)

    with TestClient(app) as client:
        response = client.post("/guess", json={"word": "  밤  "})

    assert received_words == ["밤"]
    assert response.status_code == 200
    assert [entry["sense_no"] for entry in response.json()["entries"]] == [1, 2]


def test_guess_rejects_word_that_becomes_empty_after_trimming() -> None:
    """공백만 있는 입력은 사전 조회 전에 거절한다."""
    with TestClient(app) as client:
        response = client.post("/guess", json={"word": "   "})

    assert response.status_code == 422
    assert response.json()["detail"] == "추측 단어를 입력해 주세요."


def test_guess_caches_unknown_word_then_returns_it(monkeypatch) -> None:
    """사전에 없는 단어는 한 번 캐싱한 뒤 채점 결과를 반환한다."""
    cached_words: list[str] = []

    def fake_lookup(word: str) -> list[dict[str, object]]:
        if not cached_words:
            return []
        return [
            {
                "word": word,
                "sense_no": 0,
                "definition": word,
                "similarity": -0.04,
                "on_map": False,
                "map_x": None,
                "map_y": None,
            }
        ]

    def fake_cache(word: str, embedding_model: object) -> None:
        assert embedding_model is not None
        cached_words.append(word)

    monkeypatch.setattr("backend.app.api.guess.lookup_scored_entries", fake_lookup)
    monkeypatch.setattr("backend.app.api.guess.cache_unknown_entry", fake_cache)

    with TestClient(app) as client:
        response = client.post("/guess", json={"word": "없는말"})

    assert response.status_code == 200
    assert cached_words == ["없는말"]
    assert response.json()["entries"][0]["word"] == "없는말"
