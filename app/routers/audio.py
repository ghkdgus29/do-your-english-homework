"""안드로이드 크롬의 webm 녹음을 카톡에서 재생되는 m4a로 변환. 서버에 남기지 않는다."""

import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response

from app.auth import CurrentMember

router = APIRouter(prefix="/api/audio")

MAX_BYTES = 30 * 1024 * 1024


@router.post("/convert")
async def convert(request: Request, _member: CurrentMember):
    data = await request.body()
    if not data:
        raise HTTPException(400, "빈 녹음")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "녹음이 너무 길어요")
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "in", Path(tmp) / "out.m4a"
        src.write_bytes(data)
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
            "-vn", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dst),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )  # fmt: skip
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(400, f"변환 실패: {stderr.decode(errors='ignore')[:300]}")
        return Response(await asyncio.to_thread(dst.read_bytes), media_type="audio/mp4")
