import hashlib
import hmac
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Response
from sqlmodel import Session, select

from app.db import get_session
from app.models import Member
from app.settings import settings

MEMBER_COOKIE = "member_token"
ADMIN_COOKIE = "admin_session"
ONE_YEAR = 60 * 60 * 24 * 365


def _set_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def set_member_cookie(response: Response, token: str) -> None:
    _set_cookie(response, MEMBER_COOKIE, token, ONE_YEAR)


def _admin_signature() -> str:
    # 비번이나 secret_key가 바뀌면 기존 어드민 세션이 무효가 된다
    msg = f"admin:{settings.admin_password}".encode()
    return hmac.new(settings.secret_key.encode(), msg, hashlib.sha256).hexdigest()


def check_admin_password(password: str) -> bool:
    return hmac.compare_digest(password.encode(), settings.admin_password.encode())


def set_admin_cookie(response: Response) -> None:
    _set_cookie(response, ADMIN_COOKIE, _admin_signature(), 60 * 60 * 24 * 30)


def current_member(
    session: Annotated[Session, Depends(get_session)],
    member_token: Annotated[str | None, Cookie()] = None,
) -> Member:
    if not member_token:
        raise HTTPException(401, "개인 링크로 먼저 접속해 주세요")
    member = session.exec(select(Member).where(Member.token == member_token)).first()
    if member is None:
        raise HTTPException(401, "링크가 만료됐어요. 새 링크를 받아 주세요")
    return member


def require_admin(admin_session: Annotated[str | None, Cookie()] = None) -> None:
    if not admin_session or not hmac.compare_digest(admin_session, _admin_signature()):
        raise HTTPException(401, "어드민 로그인이 필요해요")


CurrentMember = Annotated[Member, Depends(current_member)]
SessionDep = Annotated[Session, Depends(get_session)]
