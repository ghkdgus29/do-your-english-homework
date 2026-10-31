import hashlib
import hmac
import time
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Response
from sqlmodel import Session, select

from app.db import get_session
from app.models import Member
from app.settings import settings

MEMBER_COOKIE = "member_token"
ADMIN_COOKIE = "admin_session"
ONE_DAY = 60 * 60 * 24
ONE_YEAR = ONE_DAY * 365
# 어드민 세션: 30일 안 쓰면 만료, 쓰면 연장. 로그인 후 90일이 지나면 무조건 재로그인.
ADMIN_IDLE = ONE_DAY * 30
ADMIN_MAX = ONE_DAY * 90


def _now() -> int:
    return int(time.time())


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


# ---- 어드민 세션 쿠키: "<로그인 시각>.<마지막 활동 시각>.<서명>" (초 단위 unix time) ----


def _admin_signature(login_at: int, seen_at: int) -> str:
    # 비번이나 secret_key가 바뀌면 기존 어드민 세션이 무효가 된다
    msg = f"admin:{settings.admin_password}:{login_at}:{seen_at}".encode()
    return hmac.new(settings.secret_key.encode(), msg, hashlib.sha256).hexdigest()


def admin_cookie_value(login_at: int, seen_at: int) -> str:
    return f"{login_at}.{seen_at}.{_admin_signature(login_at, seen_at)}"


def _parse_admin_cookie(value: str) -> tuple[int, int] | None:
    """서명이 맞으면 (login_at, seen_at), 아니면 None."""
    try:
        login_s, seen_s, sig = value.split(".")
        login_at, seen_at = int(login_s), int(seen_s)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _admin_signature(login_at, seen_at)):
        return None
    return login_at, seen_at


def check_admin_password(password: str) -> bool:
    return hmac.compare_digest(password.encode(), settings.admin_password.encode())


def set_admin_cookie(response: Response, login_at: int | None = None) -> None:
    now = _now()
    login_at = now if login_at is None else login_at
    # 브라우저 만료는 서버 기준(활동 30일, 로그인 90일) 중 먼저 오는 쪽에 맞춘다
    max_age = max(0, min(ADMIN_IDLE, login_at + ADMIN_MAX - now))
    _set_cookie(response, ADMIN_COOKIE, admin_cookie_value(login_at, now), max_age)


def current_member(
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    member_token: Annotated[str | None, Cookie()] = None,
) -> Member:
    if not member_token:
        raise HTTPException(401, "개인 링크로 먼저 접속해 주세요")
    member = session.exec(select(Member).where(Member.token == member_token)).first()
    if member is None:
        raise HTTPException(401, "링크가 만료됐어요. 새 링크를 받아 주세요")
    # 접속할 때마다 만료를 1년 뒤로 연장 (값은 그대로)
    set_member_cookie(response, member.token)
    return member


def require_admin(response: Response, admin_session: Annotated[str | None, Cookie()] = None) -> None:
    parsed = _parse_admin_cookie(admin_session) if admin_session else None
    if parsed is None:
        raise HTTPException(401, "어드민 로그인이 필요해요")
    login_at, seen_at = parsed
    now = _now()
    if now - seen_at > ADMIN_IDLE or now - login_at > ADMIN_MAX:
        raise HTTPException(401, "어드민 세션이 만료됐어요. 다시 로그인해 주세요")
    # 요청마다 마지막 활동 시각을 갱신해 만료를 연장 (login_at은 유지)
    set_admin_cookie(response, login_at)


CurrentMember = Annotated[Member, Depends(current_member)]
SessionDep = Annotated[Session, Depends(get_session)]
