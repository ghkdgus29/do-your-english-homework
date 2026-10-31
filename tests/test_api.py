import shutil
from datetime import timedelta

import pytest
from sqlmodel import Session

from app.content import grade
from app.db import engine
from app.models import CardReview, Week, utcnow
from tests.conftest import SAMPLE_CONTENT


def _admin_login(client):
    assert client.post("/api/admin/login", json={"password": "admin-pw"}).status_code == 200


def _ready_week() -> int:
    with Session(engine) as s:
        week = Week(title="Week 49", status="ready", content=SAMPLE_CONTENT)
        s.add(week)
        s.commit()
        s.refresh(week)
        return week.id  # type: ignore[return-value]


def _member_client(client):
    _admin_login(client)
    token = client.post("/api/admin/members", json={"name": "kyle"}).json()["token"]
    client.cookies.clear()
    assert client.post("/api/join", json={"token": token}).status_code == 200
    return token


def test_admin_requires_password(client):
    client.cookies.clear()
    assert client.get("/api/admin/weeks").status_code == 401
    assert client.post("/api/admin/login", json={"password": "nope"}).status_code == 401
    _admin_login(client)
    assert client.get("/api/admin/weeks").status_code == 200


def test_member_cookie_refreshed_on_each_request(client):
    token = _member_client(client)
    r = client.get("/api/me")
    assert r.status_code == 200
    assert r.cookies.get("member_token") == token  # 값은 그대로, 만료만 연장
    assert "max-age=31536000" in r.headers["set-cookie"].lower()


def test_admin_session_expiry(client):
    from app import auth

    now = auth._now()
    day = auth.ONE_DAY

    def with_cookie(login_at, seen_at):
        client.cookies.clear()
        client.cookies.set("admin_session", auth.admin_cookie_value(login_at, seen_at))
        return client.get("/api/admin/weeks")

    # 30일 안 쓰면 만료
    assert with_cookie(now - 40 * day, now - 31 * day).status_code == 401
    # 활동은 최근이어도 로그인 90일이 지나면 만료
    assert with_cookie(now - 91 * day, now - 3600).status_code == 401
    # 서명이 틀리면 거부 (마지막 글자를 반드시 다른 값으로)
    valid = auth.admin_cookie_value(now, now)
    tampered = valid[:-1] + ("0" if valid[-1] != "0" else "1")
    client.cookies.clear()
    client.cookies.set("admin_session", tampered)
    assert client.get("/api/admin/weeks").status_code == 401

    # 유효하면 요청마다 연장 (login_at은 유지, seen_at은 갱신)
    login_at = now - 10 * day
    r = with_cookie(login_at, now - 5 * day)
    assert r.status_code == 200
    new_login, new_seen, _ = r.cookies["admin_session"].split(".")
    assert int(new_login) == login_at and int(new_seen) >= now


def test_logs_go_to_rotating_file():
    import logging

    from app.settings import settings

    logging.getLogger("app.test").info("hello-log-file")
    log_file = settings.log_dir / "app.log"
    assert log_file.exists()
    assert "INFO app.test: hello-log-file" in log_file.read_text(encoding="utf-8")


def test_member_cannot_upload(client):
    _member_client(client)
    r = client.post("/api/admin/weeks", files=[("files", ("a.jpg", b"x", "image/jpeg"))])
    assert r.status_code == 401


def test_regenerate_invalidates_old_link(client):
    _admin_login(client)
    m = client.post("/api/admin/members", json={"name": "a"}).json()
    client.post(f"/api/admin/members/{m['id']}/regenerate")
    assert client.post("/api/join", json={"token": m["token"]}).status_code == 404


def test_homework_flow_completes(client):
    week_id = _ready_week()
    _member_client(client)

    weeks = client.get("/api/weeks").json()
    assert any(w["id"] == week_id and not w["status"]["completed"] for w in weeks)

    r = client.post(f"/api/weeks/{week_id}/peek", json={"index": 1}).json()
    assert r["words"]["1"]["peeks"] == 1

    r = client.put(
        f"/api/weeks/{week_id}/answer",
        json={"words": {"0": {"meaning": "공작", "sentence": "I saw a peacock."}, "1": {"meaning": "지속되다", "sentence": "It lasts."}}},
    ).json()
    assert r["status"]["words"] and r["words"]["1"]["peeks"] == 1
    assert not r["status"]["completed"]

    client.put(f"/api/weeks/{week_id}/answer", json={"diary": "Today I coded."})
    r = client.post(f"/api/weeks/{week_id}/recording-shared").json()
    assert r["status"] == {"words": True, "recording": True, "diary": True, "completed": True}


def test_answer_rejects_unknown_word(client):
    week_id = _ready_week()
    _member_client(client)
    r = client.put(f"/api/weeks/{week_id}/answer", json={"words": {"9": {"meaning": "x"}}})
    assert r.status_code == 400


def test_cards_srs(client):
    week_id = _ready_week()
    _member_client(client)
    week_cards = client.get(f"/api/cards?week_id={week_id}").json()
    assert len(week_cards) == 2
    key = week_cards[0]["key"]

    assert client.post(f"/api/cards/{key}/grade", json={"known": True}).json()["interval_days"] == 1
    due_keys = {c["key"] for c in client.get("/api/cards").json()}
    assert key not in due_keys and week_cards[1]["key"] in due_keys


def test_grade_schedule():
    r = CardReview(member_id=1, week_id=1, card_key="1:0:0")
    now = utcnow()
    grade(r, True, now)
    grade(r, True, now)
    assert r.interval_days == 3
    grade(r, True, now)
    assert r.interval_days > 3
    grade(r, False, now)
    assert r.reps == 0 and r.due_at == now + timedelta(minutes=10)


def test_admin_content_validation(client):
    week_id = _ready_week()
    _admin_login(client)
    assert client.put(f"/api/admin/weeks/{week_id}/content", json={"week_title": "x"}).status_code == 422
    edited = {**SAMPLE_CONTENT, "week_title": "Week 50"}
    assert client.put(f"/api/admin/weeks/{week_id}/content", json=edited).json()["title"] == "Week 50"


def test_recording(client):
    week_id = _ready_week()  # script가 homework 바로 아래 있는 예전 저장 형식
    _member_client(client)
    hw = client.get(f"/api/weeks/{week_id}").json()["content"]["homework"]
    assert "script" not in hw
    assert hw["recording"] == {"type": "read", "script": SAMPLE_CONTENT["homework"]["script"], "questions": []}

    _admin_login(client)
    legacy_hw = {**SAMPLE_CONTENT["homework"], "recording_type": "answer", "script": "", "questions": ["Old?"]}
    r = client.put(f"/api/admin/weeks/{week_id}/content", json={**SAMPLE_CONTENT, "homework": legacy_hw})
    assert r.json()["content"]["homework"]["recording"] == {"type": "answer", "script": "", "questions": ["Old?"]}

    base_hw = {"title": "Review", "words": SAMPLE_CONTENT["homework"]["words"]}
    answer_hw = {**base_hw, "recording": {"type": "answer", "script": "", "questions": ["What is rich?"]}}
    r = client.put(f"/api/admin/weeks/{week_id}/content", json={**SAMPLE_CONTENT, "homework": answer_hw})
    assert r.json()["content"]["homework"]["recording"]["questions"] == ["What is rich?"]
    bad_hw = {**base_hw, "recording": {"type": "sing"}}
    assert client.put(f"/api/admin/weeks/{week_id}/content", json={**SAMPLE_CONTENT, "homework": bad_hw}).status_code == 422
    mixed_hw = {**answer_hw, "script": "x"}  # 새 형식에 옛 키가 섞이면 거부
    assert client.put(f"/api/admin/weeks/{week_id}/content", json={**SAMPLE_CONTENT, "homework": mixed_hw}).status_code == 422


def test_reextract_starts_task(client, monkeypatch):
    calls = []

    async def fake_run(week_id):
        calls.append(week_id)

    monkeypatch.setattr("app.extraction.run_extraction", fake_run)
    week_id = _ready_week()
    _admin_login(client)
    r = client.post(f"/api/admin/weeks/{week_id}/reextract")
    assert r.status_code == 200 and r.json()["status"] == "processing"
    assert client.post(f"/api/admin/weeks/{week_id}/reextract").status_code == 409
    assert calls == [week_id]


def _ffmpeg_works() -> bool:
    import subprocess

    if shutil.which("ffmpeg") is None:
        return False
    return subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _ffmpeg_works(), reason="ffmpeg 실행 불가")
def test_audio_convert(client, tmp_path):
    import subprocess

    src = tmp_path / "a.webm"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=1", "-c:a", "libopus", str(src)],
        check=True,
    )
    _member_client(client)
    r = client.post("/api/audio/convert", content=src.read_bytes())
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mp4"
