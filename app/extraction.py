"""수업 사진 → 주차 콘텐츠 JSON 추출 (Claude Agent SDK).

Claude는 week 업로드 폴더 안에서 Read 도구로 이미지만 읽고, output_format 스키마에 맞춘 JSON을 돌려준다.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from PIL import Image, ImageOps
from sqlmodel import Session

from app.db import engine
from app.models import Week
from app.settings import settings

log = logging.getLogger(__name__)

MAX_EDGE = 2000
# Read 결과로 이미지가 base64로 실려 와서, 여러 장을 한 번에 읽으면 SDK 기본 버퍼(1MB)를 넘는다
MAX_BUFFER_BYTES = 32 * 1024 * 1024

CONTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["week_title", "study_sets", "homework"],
    "properties": {
        "week_title": {"type": "string"},
        "study_sets": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "items"],
                "properties": {
                    "title": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["phrase", "meaning", "example"],
                            "properties": {
                                "phrase": {"type": "string"},
                                "meaning": {"type": "string"},
                                "example": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "homework": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "words", "recording_type", "script", "questions"],
            "properties": {
                "title": {"type": "string"},
                "words": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["word", "hint", "meaning"],
                        "properties": {
                            "word": {"type": "string"},
                            "hint": {"type": "string"},
                            "meaning": {"type": "string"},
                        },
                    },
                },
                "recording_type": {"type": "string", "enum": ["read", "answer"]},
                "script": {"type": "string"},
                "questions": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}

PROMPT = """\
이 폴더에는 영어 회화 수업 자료 사진 {count}장이 있어: {files}
Read 도구로 모든 사진을 직접 읽고, 아래 규칙대로 JSON을 만들어줘.

공통 규칙
- 인쇄된 글자만 옮겨. 학생이 손으로 쓴 필기·이름·낙서는 전부 무시해.
- 워터마크(wg. With gloria 등)도 무시해.
- 철자·문장부호는 인쇄본 그대로 정확히 옮겨.

사진 분류
- "숙제지": word/meaning/sentence 표, 녹음(Read!) 스크립트, Diary 칸이 있는 페이지. 보통 1장.
- 나머지는 "외우기 자료"(숙어·패턴 페이지 등).

study_sets (외우기 자료 1장 = 1세트)
- title: 페이지 제목 그대로 (예: "Week 49. Idioms 15 [숙어]", "Pattern 12 : Negotiation 협상하기").
- items: 외워야 할 표현 하나당 1개.
  - phrase: 영어 표현 (예: "cover up", "~is not acceptable.").
  - meaning: 인쇄된 한국어 뜻. 인쇄된 뜻이 없으면 자연스러운 한국어 뜻을 직접 써줘.
  - example: 인쇄된 영어 예문. 질문 문장 안에서 쓰인 표현이면 그 질문 문장 전체. 없으면 "".
- 숙어 표 안의 표현뿐 아니라, Group Talk 질문 속 굵게 표시된 표현(괄호 안 한국어 뜻이 붙은 것)도 각각 item으로 넣어. 같은 표현이 여러 질문에 나오면 1번만.
- "What did you do last week" 같은 안부/Catch Up 섹션은 넣지 마.

homework (숙제지)
- title: 숙제지 제목 (예: "Review 월요일 - September 21st / Class: September 28th").
- words: 표의 단어 순서대로.
  - word: 영어 단어/표현.
  - hint: meaning 칸에 미리 인쇄돼 있는 힌트(예: "동사"). 없으면 "".
  - meaning: 학생이 정답 확인용으로 볼 간결한 한국어 뜻. hint가 있으면 그 품사의 뜻으로. (예: last + 동사 → "지속되다, 계속되다")
- 녹음 숙제는 두 종류야. "녹음:" 뒤 지시문을 보고 분류해.
  - "Read!"처럼 스크립트를 따라 읽는 숙제 → recording_type "read", script에 본문 전체 (제목 제외, 줄바꿈 없이 한 문단), questions는 [].
  - "Answer the questions!"처럼 질문에 대답하는 숙제 → recording_type "answer", questions에 질문을 글머리 기호 한 줄당 1개씩 (한 줄에 질문이 여러 개면 그대로 한 항목), script는 "".

week_title: 외우기 자료 제목에서 주차를 뽑아 짧게 (예: "Week 49"). 없으면 숙제지 수업 날짜.
"""


def prepare_images(raw_paths: list[Path], dest_dir: Path) -> list[str]:
    """EXIF 회전 보정 + 긴 변 2000px로 줄여 JPEG로 저장. 원본은 지운다."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    names = []
    for i, raw in enumerate(raw_paths, start=1):
        name = f"page{i}.jpg"
        with Image.open(raw) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            img.thumbnail((MAX_EDGE, MAX_EDGE))
            img.save(dest_dir / name, "JPEG", quality=85)
        raw.unlink(missing_ok=True)
        names.append(name)
    return names


async def extract_content(image_dir: Path, images: list[str]) -> dict[str, Any]:
    options = ClaudeAgentOptions(
        cwd=str(image_dir),
        tools=["Read"],
        allowed_tools=["Read"],
        output_format={"type": "json_schema", "schema": CONTENT_SCHEMA},
        max_turns=15,
        max_buffer_size=MAX_BUFFER_BYTES,
        model=settings.claude_model,
        cli_path=settings.claude_cli_path,
    )
    prompt = PROMPT.format(count=len(images), files=", ".join(images))
    result: ResultMessage | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message
    if result is None or result.is_error or result.structured_output is None:
        detail = (result.errors or result.result) if result else "no result"
        raise RuntimeError(f"추출 실패: {detail}")
    log.info("extraction done: turns=%s cost=%s", result.num_turns, result.total_cost_usd)
    return result.structured_output


async def run_extraction(week_id: int) -> None:
    with Session(engine) as session:
        week = session.get(Week, week_id)
        assert week is not None
        images = list(week.images)
    image_dir = settings.upload_dir / str(week_id)
    try:
        content = await extract_content(image_dir, images)
    except Exception as e:  # noqa: BLE001  실패 사유를 어드민 화면에 보여준다
        log.exception("extraction failed for week %s", week_id)
        with Session(engine) as session:
            week = session.get(Week, week_id)
            if week:
                week.status, week.error = "failed", str(e)[:2000]
                session.add(week)
                session.commit()
        return
    with Session(engine) as session:
        week = session.get(Week, week_id)
        if week:
            week.content = content
            week.title = content.get("week_title") or week.title
            week.status, week.error = "ready", None
            session.add(week)
            session.commit()


_tasks: set[asyncio.Task] = set()


def start_extraction(week_id: int) -> None:
    task = asyncio.create_task(run_extraction(week_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
