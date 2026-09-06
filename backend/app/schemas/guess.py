"""추측 API의 요청·응답 형식을 정의한다."""

from pydantic import BaseModel


class GuessRequest(BaseModel):
    """사용자가 보낸 추측 입력이다."""

    word: str


class ScoredEntry(BaseModel):
    """정답과의 similarity를 포함한 entry 응답이다."""

    word: str
    sense_no: int
    definition: str
    similarity: float
    on_map: bool
    map_x: float | None
    map_y: float | None


class GuessResponse(BaseModel):
    """한 추측에서 찾은 모든 sense의 채점 결과다."""

    entries: list[ScoredEntry]
