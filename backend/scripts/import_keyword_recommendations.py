"""
Import keyword_recommendations.csv into the SQLite movie_recommendations table.

This is the MovieCrew version (SQLite + SQLAlchemy schema).
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movie_recommendations (
  movie_id INTEGER NOT NULL,
  recommended_movie_id INTEGER NOT NULL,
  similarity_score REAL,
  PRIMARY KEY (movie_id, recommended_movie_id)
);
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to keyword_recommendations.csv")
    ap.add_argument("--sqlite", required=True, help="Path to movie_db.sqlite3")
    ap.add_argument("--batch", type=int, default=5000, help="Batch size (default 5000)")
    args = ap.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    sqlite_path = Path(args.sqlite).expanduser().resolve()
    if not csv_path.exists():
        raise SystemExit(f"Missing CSV: {csv_path}")
    if not sqlite_path.exists():
        raise SystemExit(f"Missing SQLite DB: {sqlite_path}")

    con = sqlite3.connect(str(sqlite_path))
    try:
        cur = con.cursor()
        cur.execute(CREATE_TABLE_SQL)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_movie_reco_recommended_movie_id ON movie_recommendations(recommended_movie_id);"
        )
        con.commit()

        inserted = 0
        batch: list[tuple[int, int, float | None]] = []
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                movie_id = int(row["movie_id"])
                rec_id = int(row["recommended_movie_id"])
                score_raw = (row.get("similarity_score") or "").strip()
                score = float(score_raw) if score_raw else None
                batch.append((movie_id, rec_id, score))
                if len(batch) >= int(args.batch):
                    cur.executemany(
                        "INSERT OR REPLACE INTO movie_recommendations(movie_id, recommended_movie_id, similarity_score) "
                        "VALUES (?, ?, ?);",
                        batch,
                    )
                    inserted += len(batch)
                    batch.clear()
        if batch:
            cur.executemany(
                "INSERT OR REPLACE INTO movie_recommendations(movie_id, recommended_movie_id, similarity_score) "
                "VALUES (?, ?, ?);",
                batch,
            )
            inserted += len(batch)
        con.commit()
        print(f"Imported {inserted} recommendations into {sqlite_path}.")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())

