from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import select

from app.auth import CurrentMember, SessionDep, set_member_cookie
from app.content import WeekContent, grade, homework_status, is_due, iter_cards
from app.models import CardReview, HomeworkAnswer, Member, Week, utcnow

router = APIRouter(prefix="/api")


class JoinIn(BaseModel):
    token: str


@router.post("/join")
def join(body: JoinIn, response: Response, session: SessionDep):
    member = session.exec(select(Member).where(Member.token == body.token)).first()
    if member is None:
        raise HTTPException(404, "유효하지 않은 링크예요")
    set_member_cookie(response, member.token)
    return {"id": member.id, "name": member.name}


@router.get("/me")
def me(member: CurrentMember):
    return {"id": member.id, "name": member.name}


def _ready_week(session: SessionDep, week_id: int) -> tuple[Week, WeekContent]:
    week = session.get(Week, week_id)
    if week is None or week.status != "ready" or not week.content:
        raise HTTPException(404, "주차를 찾을 수 없어요")
    return week, WeekContent.model_validate(week.content)


def _answer(session: SessionDep, member: Member, week_id: int) -> HomeworkAnswer | None:
    return session.exec(
        select(HomeworkAnswer).where(
            HomeworkAnswer.member_id == member.id, HomeworkAnswer.week_id == week_id
        )
    ).first()


def _answer_or_new(session: SessionDep, member: Member, week_id: int) -> HomeworkAnswer:
    return _answer(session, member, week_id) or HomeworkAnswer(member_id=member.id, week_id=week_id)


def _answer_out(answer: HomeworkAnswer | None, content: WeekContent) -> dict:
    return {
        "words": answer.words if answer else {},
        "diary": answer.diary if answer else "",
        "recording_shared": bool(answer and answer.recording_shared),
        "status": homework_status(content, answer),
    }


def _save_answer(session: SessionDep, answer: HomeworkAnswer, content: WeekContent) -> dict:
    status = homework_status(content, answer)
    if status["completed"] and answer.completed_at is None:
        answer.completed_at = utcnow()
    answer.updated_at = utcnow()
    session.add(answer)
    session.commit()
    session.refresh(answer)
    return _answer_out(answer, content)


@router.get("/weeks")
def list_weeks(member: CurrentMember, session: SessionDep):
    weeks = session.exec(
        select(Week).where(Week.status == "ready").order_by(Week.created_at.desc())  # type: ignore[attr-defined]
    ).all()
    out = []
    for week in weeks:
        content = WeekContent.model_validate(week.content)
        out.append(
            {
                "id": week.id,
                "title": week.title,
                "homework_title": content.homework.title,
                "created_at": week.created_at,
                "card_count": sum(len(s.items) for s in content.study_sets),
                "status": homework_status(content, _answer(session, member, week.id)),  # type: ignore[arg-type]
            }
        )
    return out


@router.get("/weeks/{week_id}")
def get_week(week_id: int, member: CurrentMember, session: SessionDep):
    week, content = _ready_week(session, week_id)
    return {
        "id": week.id,
        "title": week.title,
        "content": content.model_dump(),
        "answer": _answer_out(_answer(session, member, week_id), content),
    }


class WordIn(BaseModel):
    meaning: str = ""
    sentence: str = ""


class AnswerIn(BaseModel):
    # 단어 인덱스(str) -> 답. 보낸 단어만 갱신한다.
    words: dict[str, WordIn] | None = None
    diary: str | None = None


@router.put("/weeks/{week_id}/answer")
def save_answer(week_id: int, body: AnswerIn, member: CurrentMember, session: SessionDep):
    _, content = _ready_week(session, week_id)
    answer = _answer_or_new(session, member, week_id)
    if body.words:
        for idx, w in body.words.items():
            if not idx.isdigit() or int(idx) >= len(content.homework.words):
                raise HTTPException(400, f"없는 단어 번호: {idx}")
            answer.set_word(int(idx), w.meaning, w.sentence)
    if body.diary is not None:
        answer.diary = body.diary
    return _save_answer(session, answer, content)


class PeekIn(BaseModel):
    index: int


@router.post("/weeks/{week_id}/peek")
def peek(week_id: int, body: PeekIn, member: CurrentMember, session: SessionDep):
    _, content = _ready_week(session, week_id)
    if not 0 <= body.index < len(content.homework.words):
        raise HTTPException(400, "없는 단어 번호")
    answer = _answer_or_new(session, member, week_id)
    answer.add_peek(body.index)
    return _save_answer(session, answer, content)


@router.post("/weeks/{week_id}/recording-shared")
def recording_shared(week_id: int, member: CurrentMember, session: SessionDep):
    _, content = _ready_week(session, week_id)
    answer = _answer_or_new(session, member, week_id)
    answer.recording_shared = True
    return _save_answer(session, answer, content)


@router.get("/cards")
def list_cards(member: CurrentMember, session: SessionDep, week_id: int | None = None):
    """week_id가 있으면 그 주차 카드 전부, 없으면 전 주차에서 복습할 때가 된 카드(SRS)."""
    query = select(Week).where(Week.status == "ready")
    if week_id is not None:
        query = query.where(Week.id == week_id)
    weeks = session.exec(query).all()
    reviews = {
        r.card_key: r
        for r in session.exec(select(CardReview).where(CardReview.member_id == member.id)).all()
    }
    now = utcnow()
    cards = []
    for week in weeks:
        content = WeekContent.model_validate(week.content)
        for key, set_title, item in iter_cards(week.id, content):  # type: ignore[arg-type]
            review = reviews.get(key)
            if week_id is None and not is_due(review, now):
                continue
            cards.append(
                {
                    "key": key,
                    "week_title": week.title,
                    "set_title": set_title,
                    **item.model_dump(),
                    "is_new": review is None,
                    "reps": review.reps if review else 0,
                }
            )
    # 복습 카드 먼저, 새 카드는 뒤로
    cards.sort(key=lambda c: c["is_new"])
    return cards


@router.get("/cards/due-count")
def due_count(member: CurrentMember, session: SessionDep):
    return {"count": len(list_cards(member, session))}


class GradeIn(BaseModel):
    known: bool


@router.post("/cards/{key}/grade")
def grade_card(key: str, body: GradeIn, member: CurrentMember, session: SessionDep):
    try:
        week_id, set_idx, item_idx = (int(p) for p in key.split(":"))
    except ValueError:
        raise HTTPException(400, "잘못된 카드")
    _, content = _ready_week(session, week_id)
    if set_idx >= len(content.study_sets) or item_idx >= len(content.study_sets[set_idx].items):
        raise HTTPException(404, "없는 카드")
    review = session.exec(
        select(CardReview).where(CardReview.member_id == member.id, CardReview.card_key == key)
    ).first() or CardReview(member_id=member.id, week_id=week_id, card_key=key)  # type: ignore[arg-type]
    grade(review, body.known)
    session.add(review)
    session.commit()
    return {"interval_days": review.interval_days}
