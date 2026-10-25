import os
import tempfile

os.environ.update(
    DATA_DIR=tempfile.mkdtemp(),
    ADMIN_PASSWORD="admin-pw",
    SECRET_KEY="test-secret",
    COOKIE_SECURE="false",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SAMPLE_CONTENT = {
    "week_title": "Week 49",
    "study_sets": [
        {
            "title": "Pattern 12 : Negotiation 협상하기",
            "items": [
                {"phrase": "~is not acceptable.", "meaning": "~은 받아들일 수 없습니다.", "example": "Working overtime every night is not acceptable."},
                {"phrase": "~is a low priority.", "meaning": "~은 중요하지 않습니다.", "example": "The contract period is a low priority."},
            ],
        }
    ],
    "homework": {
        "title": "Review 월요일",
        "words": [
            {"word": "peacock", "hint": "", "meaning": "공작"},
            {"word": "last", "hint": "동사", "meaning": "지속되다"},
        ],
        "script": "Since I moved into a new apartment, I've also got new neighbors.",
    },
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
