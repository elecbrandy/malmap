"""런타임 E5 임베딩을 생성한다."""

from typing import Any

MODEL_NAME = "intfloat/multilingual-e5-base"
EMBEDDING_DIMENSION = 768


def load_embedding_model() -> Any:
    """파이프라인과 같은 E5 모델을 앱 시작 시 한 번 로드한다.

    Returns:
        정규화 임베딩을 생성할 SentenceTransformer 모델.

    Raises:
        RuntimeError: 모델 차원이 DB 스키마와 다른 경우.
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)
    embedding_dimension = model.get_embedding_dimension()
    if embedding_dimension != EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"임베딩 차원이 {embedding_dimension}입니다. "
            f"DB 스키마의 VECTOR({EMBEDDING_DIMENSION})와 일치하지 않습니다."
        )
    return model


def create_unknown_entry_embedding(model: Any, word: str) -> list[float]:
    """사전에 없는 word를 파이프라인과 같은 형식으로 임베딩한다.

    뜻풀이가 없으므로 표기 자체를 임시 뜻풀이로 사용하되, 파이프라인과
    같은 `query: 표제어: 뜻풀이` 구조와 L2 정규화를 유지한다.

    Args:
        model: 앱 시작 시 로드한 E5 모델.
        word: 사전에 없는, 공백 정리된 추측 표기.

    Returns:
        DB에 저장할 768차원 정규화 임베딩.

    Raises:
        RuntimeError: 모델이 반환한 차원이 DB 스키마와 다른 경우.
    """
    embedding = model.encode(
        [f"query: {word}: {word}"],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )[0].tolist()
    if len(embedding) != EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"임베딩 차원이 {len(embedding)}입니다. "
            f"DB 스키마의 VECTOR({EMBEDDING_DIMENSION})와 일치하지 않습니다."
        )
    return embedding
