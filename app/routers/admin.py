import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
from sqlmodel import delete, select

from app.auth import ADMIN_COOKIE, SessionDep, check_admin_password, require_admin, set_admin_cookie
from app.content import WeekContent
from app.extraction import prepare_images, start_extraction
from app.models import CardReview, HomeworkAnswer, Member, Week, new_token
from app.settings import settings

router = APIRouter(prefix="/api/admin")
protected = APIRouter(dependencies=[Depends(require_admin)])

MAX_IMAGES = 5
MAX_IMAGE_BYTES = 25 * 1024 * 1024


class LoginIn(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginIn, response: Response):
    if not check_admin_password(body.password):
        raise HTTPException(401, "비밀번호가 틀렸어요")
    set_admin_cookie(response)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(ADMIN_COOKIE)
    return {"ok": True}


@protected.get("/me")
def admin_me():
    return {"ok": True}


# ---- 주차 ----


def _week_out(week: Week) -> dict:
    return {
        "id": week.id,
        "title": week.title,
        "status": week.status,
        "error": week.error,
        "images": week.images,
        "content": week.content,
        "created_at": week.created_at,
    }


def _get_week(session: SessionDep, week_id: int) -> Week:
    week = session.get(Week, week_id)
    if week is None:
        raise HTTPException(404, "주차 없음")
    return week


@protected.get("/weeks")
def list_weeks(session: SessionDep):
    weeks = session.exec(select(Week).order_by(Week.created_at.desc())).all()  # type: ignore[attr-defined]
    return [_week_out(w) for w in weeks]


@protected.post("/weeks")
async def create_week(session: SessionDep, files: Annotated[list[UploadFile], File()]):
    if not 1 <= len(files) <= MAX_IMAGES:
        raise HTTPException(400, f"사진은 1~{MAX_IMAGES}장")
    blobs = [await f.read() for f in files]
    if any(len(b) > MAX_IMAGE_BYTES for b in blobs):
        raise HTTPException(400, "사진이 너무 커요 (25MB 이하)")

    week = Week()
    session.add(week)
    session.commit()
    session.refresh(week)
    assert week.id is not None

    with tempfile.TemporaryDirectory() as tmp:
        raw_paths = []
        for i, data in enumerate(blobs):
            path = Path(tmp) / f"raw{i}"
            path.write_bytes(data)
            raw_paths.append(path)
        try:
            week.images = prepare_images(raw_paths, settings.upload_dir / str(week.id))
        except Exception:
            session.delete(week)
            session.commit()
            raise HTTPException(400, "이미지를 읽을 수 없어요 (jpg/png)")
    session.add(week)
    session.commit()
    start_extraction(week.id)
    return _week_out(week)


# start_extraction이 이벤트 루프에 태스크를 거니까 async여야 한다 (sync면 스레드풀에서 돌아 루프가 없다)
@protected.post("/weeks/{week_id}/reextract")
async def reextract(week_id: int, session: SessionDep):
    week = _get_week(session, week_id)
    if week.status == "processing":
        raise HTTPException(409, "이미 추출 중이에요")
    week.status, week.error = "processing", None
    session.add(week)
    session.commit()
    start_extraction(week_id)
    return _week_out(week)


@protected.put("/weeks/{week_id}/content")
def update_content(week_id: int, body: dict, session: SessionDep):
    week = _get_week(session, week_id)
    try:
        content = WeekContent.model_validate(body)
    except ValidationError as e:
        raise HTTPException(422, str(e))
    week.content = content.model_dump()
    week.title = content.week_title
    week.status, week.error = "ready", None
    session.add(week)
    session.commit()
    return _week_out(week)


@protected.delete("/weeks/{week_id}")
def delete_week(week_id: int, session: SessionDep):
    week = _get_week(session, week_id)
    session.exec(delete(HomeworkAnswer).where(HomeworkAnswer.week_id == week_id))  # type: ignore[call-overload]
    session.exec(delete(CardReview).where(CardReview.week_id == week_id))  # type: ignore[call-overload]
    session.delete(week)
    session.commit()
    shutil.rmtree(settings.upload_dir / str(week_id), ignore_errors=True)
    return {"ok": True}


@protected.get("/weeks/{week_id}/images/{name}")
def week_image(week_id: int, name: str, session: SessionDep):
    week = _get_week(session, week_id)
    if name not in week.images:
        raise HTTPException(404)
    return FileResponse(settings.upload_dir / str(week_id) / name)


# ---- 멤버 ----


def _member_out(m: Member) -> dict:
    return {"id": m.id, "name": m.name, "token": m.token, "created_at": m.created_at}


@protected.get("/members")
def list_members(session: SessionDep):
    return [_member_out(m) for m in session.exec(select(Member).order_by(Member.id)).all()]  # type: ignore[arg-type]


class MemberIn(BaseModel):
    name: str


@protected.post("/members")
def create_member(body: MemberIn, session: SessionDep):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "이름을 입력해 주세요")
    member = Member(name=name)
    session.add(member)
    session.commit()
    session.refresh(member)
    return _member_out(member)


@protected.post("/members/{member_id}/regenerate")
def regenerate_link(member_id: int, session: SessionDep):
    member = session.get(Member, member_id)
    if member is None:
        raise HTTPException(404)
    member.token = new_token()
    session.add(member)
    session.commit()
    session.refresh(member)
    return _member_out(member)


@protected.delete("/members/{member_id}")
def delete_member(member_id: int, session: SessionDep):
    member = session.get(Member, member_id)
    if member is None:
        raise HTTPException(404)
    session.exec(delete(HomeworkAnswer).where(HomeworkAnswer.member_id == member_id))  # type: ignore[call-overload]
    session.exec(delete(CardReview).where(CardReview.member_id == member_id))  # type: ignore[call-overload]
    session.delete(member)
    session.commit()
    return {"ok": True}


router.include_router(protected)
