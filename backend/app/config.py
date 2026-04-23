from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    app_name: str = _env("APP_NAME", "MovieScope API")
    app_env: str = _env("APP_ENV", "dev")

    cors_origins: list[str] = tuple(
        origin.strip()
        for origin in _env("CORS_ORIGINS", "http://localhost:8080").split(",")
        if origin.strip()
    )  # type: ignore[assignment]

    db_type: str = _env("DB_TYPE", "sqlite").lower()

    sqlite_path: str = _env("SQLITE_PATH", "./data/movie_db.sqlite3")

    db_host: str = _env("DB_HOST", "127.0.0.1")
    db_port: int = int(_env("DB_PORT", "3306"))
    db_user: str = _env("DB_USER", "root")
    db_password: str = _env("DB_PASSWORD", "")
    db_name: str = _env("DB_NAME", "movie_db")

    api_host: str = _env("API_HOST", "127.0.0.1")
    api_port: int = int(_env("API_PORT", "8000"))

    # Used to sign session cookies (keep secret in production)
    session_secret_key: str = _env("SESSION_SECRET_KEY", "dev-change-me")

    @property
    def database_url(self) -> str:
        if self.db_type == "sqlite":
            # sqlite+pysqlite is the default SQLAlchemy sqlite driver
            # 4 slashes means "absolute path" if the path starts with /
            if self.sqlite_path.startswith("/"):
                return f"sqlite+pysqlite:///{self.sqlite_path}"
            return f"sqlite+pysqlite:///{self.sqlite_path}"

        if self.db_type == "mysql":
            return (
                f"mysql+pymysql://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )

        raise RuntimeError("DB_TYPE must be sqlite or mysql")


settings = Settings()

