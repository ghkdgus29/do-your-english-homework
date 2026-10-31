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
    # JSON 컬럼은 안쪽만 고치면 SQLAlchemy가 변경을 모른다 (UPDATE가 안 나감).
    # 그래서 바깥에서 직접 만지지 말고 아래 메서드로 새 dict를 통째로 대입한다.
    words: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    diary: str = ""
    recording_shared: bool = False
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utcnow)

    def word(self, index: int) -> dict[str, Any]:
        """index번 단어의 답 복사본. 아직 안 썼으면 빈 답."""
        return dict(self.words.get(str(index)) or {"meaning": "", "sentence": "", "peeks": 0})

    def set_word(self, index: int, meaning: str, sentence: str) -> None:
        """뜻·문장을 갱신한다. peeks는 유지."""
        self._put_word(index, {**self.word(index), "meaning": meaning, "sentence": sentence})

    def add_peek(self, index: int) -> None:
        """뜻을 훔쳐본 횟수 +1."""
        entry = self.word(index)
        self._put_word(index, {**entry, "peeks": entry["peeks"] + 1})

    def _put_word(self, index: int, entry: dict[str, Any]) -> None:
        self.words = {**self.words, str(index): entry}


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
