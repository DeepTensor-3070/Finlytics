from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    APP_NAME: str = "Finlytics API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "sqlite:///./data/finlytics.db"


    UPLOAD_DIR: str = "data/uploads"
    MAX_UPLOAD_SIZE_MB: int = Field(default=15, ge=1, le=100)


    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    TINYFISH_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def resolve_path(self, path: str) -> Path:
        """Resolve a relative storage path against the project root."""
        resolved = Path(path).expanduser()

        if not resolved.is_absolute():
            resolved = PROJECT_ROOT / resolved

        return resolved.resolve()

    @property
    def upload_path(self) -> Path:
        """Absolute directory used for uploaded documents."""
        return self.resolve_path(self.UPLOAD_DIR)

    @property
    def database_path(self) -> Path | None:
        """Absolute path for a file-backed SQLite database."""
        prefix = "sqlite:///"

        if not self.DATABASE_URL.startswith(prefix):
            return None

        raw_path = self.DATABASE_URL[len(prefix):]

        if not raw_path or raw_path == ":memory:":
            return None

        path = Path(raw_path)

        if not path.is_absolute():
            path = PROJECT_ROOT / path

        return path.resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
