from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    admin_password: str
    # 쿠키 서명용. 바꾸면 어드민 세션이 모두 풀린다.
    secret_key: str
    data_dir: Path = Path("data")
    # 로컬 http 개발 시 false
    cookie_secure: bool = True
    # 비어 있으면 CLI 기본 모델
    claude_model: str | None = None
    # 비어 있으면 SDK에 번들된 claude CLI 사용
    claude_cli_path: str | None = None

    @property
    def db_path(self) -> Path:
        return self.data_dir / "homework.db"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"


settings = Settings()  # type: ignore[call-arg]
