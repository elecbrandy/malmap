"""Supabase PostgreSQL 연결을 제공한다."""

import os
from contextlib import contextmanager
from typing import Any, Generator

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row


def get_database_url() -> str:
    """환경 변수에서 Supabase 연결 문자열을 읽는다.

    Returns:
        psycopg가 사용할 PostgreSQL 연결 문자열.

    Raises:
        HTTPException: DATABASE_URL이 설정되지 않은 경우.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL 환경 변수가 필요합니다.")
    return database_url


@contextmanager
def get_connection() -> Generator[psycopg.Connection[Any], None, None]:
    """요청 처리 중 사용할 PostgreSQL 연결을 연다.

    Returns:
        트랜잭션이 자동으로 완료되는 psycopg 연결.
    """
    with psycopg.connect(get_database_url(), row_factory=dict_row) as connection:
        yield connection
