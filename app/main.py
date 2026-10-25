import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import Week
from app.routers import admin, audio, member

logging.basicConfig(level=logging.INFO)

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    # 재시작으로 끊긴 추출 작업은 실패 처리 → 어드민에서 재추출
    with Session(engine) as session:
        for week in session.exec(select(Week).where(Week.status == "processing")).all():
            week.status, week.error = "failed", "서버 재시작으로 중단됨"
            session.add(week)
        session.commit()
    yield


app = FastAPI(title="Do Your English Homework", lifespan=lifespan)
app.include_router(member.router)
app.include_router(admin.router)
app.include_router(audio.router)


@app.get("/healthz")
def healthz():
    return {"ok": True}


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        file = (FRONTEND_DIST / path).resolve()
        if path and file.is_file() and file.is_relative_to(FRONTEND_DIST):
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html", headers={"Cache-Control": "no-cache"})
