"""주차 콘텐츠 구조와, 그 위에서 도는 숙제 완료 판정 / 플래시카드(SRS) 로직."""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models import CardReview, HomeworkAnswer, utcnow


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StudyItem(_Strict):
    phrase: str
    meaning: str
    example: str = ""


class StudySet(_Strict):
    title: str
    items: list[StudyItem]


class HomeworkWord(_Strict):
    word: str
    hint: str = ""
    meaning: str


class Homework(_Strict):
    title: str
    words: list[HomeworkWord]
    # 녹음 숙제: read = 스크립트 따라 읽기(script), answer = 질문에 대답하기(questions)
    recording_type: Literal["read", "answer"] = "read"
    script: str = ""
    questions: list[str] = []


class WeekContent(_Strict):
    week_title: str
    study_sets: list[StudySet]
    homework: Homework


# ---- 숙제 ----


def homework_status(content: WeekContent, answer: HomeworkAnswer | None) -> dict[str, bool]:
    words = answer.words if answer else {}
    words_done = all(
        (words.get(str(i)) or {}).get("meaning", "").strip()
        and (words.get(str(i)) or {}).get("sentence", "").strip()
        for i in range(len(content.homework.words))
    )
    recording_done = bool(answer and answer.recording_shared)
    diary_done = bool(answer and answer.diary.strip())
    return {
        "words": words_done,
        "recording": recording_done,
        "diary": diary_done,
        "completed": words_done and recording_done and diary_done,
    }


# ---- 플래시카드 ----


def card_key(week_id: int, set_idx: int, item_idx: int) -> str:
    return f"{week_id}:{set_idx}:{item_idx}"


def iter_cards(week_id: int, content: WeekContent):
    for s_idx, study_set in enumerate(content.study_sets):
        for i_idx, item in enumerate(study_set.items):
            yield card_key(week_id, s_idx, i_idx), study_set.title, item


def is_due(review: CardReview | None, now: datetime) -> bool:
    if review is None:
        return True
    due = review.due_at if review.due_at.tzinfo else review.due_at.replace(tzinfo=now.tzinfo)
    return due <= now


def grade(review: CardReview, known: bool, now: datetime | None = None) -> None:
    """알아요/몰라요 2단계 SM-2 변형."""
    now = now or utcnow()
    if not known:
        review.reps = 0
        review.interval_days = 0
        review.ease = max(1.3, review.ease - 0.2)
        review.due_at = now + timedelta(minutes=10)
        return
    review.reps += 1
    if review.reps == 1:
        review.interval_days = 1
    elif review.reps == 2:
        review.interval_days = 3
    else:
        review.interval_days = round(review.interval_days * review.ease, 1)
    review.ease = min(3.0, review.ease + 0.05)
    review.due_at = now + timedelta(days=review.interval_days)
