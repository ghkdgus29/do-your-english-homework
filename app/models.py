import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_token() -> str:
    return secrets.token_urlsafe(24)


class Member(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    # 개인 링크(/join/{token})이자 로그인 쿠키 값. 재발급하면 기존 링크·기기 모두 로그아웃.
    token: str = Field(default_factory=new_token, index=True, unique=True)
    created_at: datetime = Field(default_factory=utcnow)


class Week(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = "추출 중..."
    # processing | ready | failed
    status: str = "processing"
    error: str | None = None
    # 업로드된 이미지 파일명 (upload_dir/{week_id}/ 아래)
    images: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    content: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class HomeworkAnswer(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("member_id", "week_id"),)

    id: int | None = Field(default=None, primary_key=True)
    member_id: int = Field(foreign_key="member.id", index=True)
    week_id: int = Field(foreign_key="week.id", index=True)
    # 단어 인덱스(str) -> {"meaning": str, "sentence": str, "peeks": int}
    words: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    diary: str = ""
    recording_shared: bool = False
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utcnow)


class CardReview(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("member_id", "card_key"),)

    id: int | None = Field(default=None, primary_key=True)
    member_id: int = Field(foreign_key="member.id", index=True)
    week_id: int = Field(foreign_key="week.id", index=True)
    # "{week_id}:{set_idx}:{item_idx}"
    card_key: str
    reps: int = 0
    interval_days: float = 0
    ease: float = 2.5
    due_at: datetime = Field(default_factory=utcnow)
