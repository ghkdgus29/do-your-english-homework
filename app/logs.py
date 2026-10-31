"""로그 설정. stderr(docker logs)와 data/logs/app.log 파일 양쪽에 남긴다.

도커 로그는 컨테이너를 재생성하면 사라지므로, 볼륨인 data/ 아래 파일로도 쌓는다.
파일은 RotatingFileHandler로 크기 상한을 두어 무한히 커지지 않는다.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.settings import settings

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
# uvicorn은 이 두 로거에 핸들러를 따로 달고 root로 전파하지 않아서, 파일에도 남기려면 직접 붙여야 한다.
# (uvicorn.error는 uvicorn으로 전파되므로 따로 붙이면 두 번 찍힌다)
UVICORN_LOGGERS = ("uvicorn", "uvicorn.access")


def configure_logging() -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(FORMAT)

    file_handler = RotatingFileHandler(
        settings.log_dir / "app.log",
        maxBytes=settings.log_max_mb * 1024 * 1024,
        backupCount=settings.log_backups,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [stderr_handler, file_handler]

    for name in UVICORN_LOGGERS:
        logger = logging.getLogger(name)
        if any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
            continue
        logger.addHandler(file_handler)
