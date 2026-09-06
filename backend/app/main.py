"""말맵 FastAPI 애플리케이션 진입점이다."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from backend.app.api.guess import router as guess_router
from backend.app.core.embedding import load_embedding_model


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """앱 시작 시 런타임 임베딩 모델을 한 번만 로드한다."""
    application.state.embedding_model = load_embedding_model()
    yield


app = FastAPI(title="말맵 API", lifespan=lifespan)
app.include_router(guess_router)
