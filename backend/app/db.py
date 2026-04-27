from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Base


connect_args = {}
if settings.db_type == "sqlite":
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)

def _ensure_sqlite_recommendation_indexes() -> None:
    if settings.db_type != "sqlite":
        return
    with engine.connect() as con:
        con.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_movie_reco_recommended_movie_id "
            "ON movie_recommendations(recommended_movie_id);"
        )

def _ensure_sqlite_user_verification_columns() -> None:
    # SQLAlchemy create_all does NOT add missing columns to existing tables.
    # For this uni project, we do a tiny “migration” for SQLite only.
    if settings.db_type != "sqlite":
        return

    with engine.connect() as con:
        cols = [row[1] for row in con.exec_driver_sql("PRAGMA table_info(users);").fetchall()]
        if "full_name" not in cols:
            con.exec_driver_sql("ALTER TABLE users ADD COLUMN full_name TEXT;")
        if "is_age_verified" not in cols:
            con.exec_driver_sql("ALTER TABLE users ADD COLUMN is_age_verified INTEGER NOT NULL DEFAULT 0;")
        if "verification_method" not in cols:
            con.exec_driver_sql("ALTER TABLE users ADD COLUMN verification_method TEXT;")
        if "verification_status" not in cols:
            con.exec_driver_sql("ALTER TABLE users ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'pending';")
        if "verified_at" not in cols:
            con.exec_driver_sql("ALTER TABLE users ADD COLUMN verified_at DATETIME;")
        if "birth_date" not in cols:
            con.exec_driver_sql("ALTER TABLE users ADD COLUMN birth_date DATE;")
        if "is_adult" not in cols:
            con.exec_driver_sql("ALTER TABLE users ADD COLUMN is_adult INTEGER NOT NULL DEFAULT 0;")


# Create any missing tables (won't overwrite existing ones).
Base.metadata.create_all(engine)
_ensure_sqlite_user_verification_columns()
_ensure_sqlite_recommendation_indexes()


@contextmanager
def get_db_session() -> Session:
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()

