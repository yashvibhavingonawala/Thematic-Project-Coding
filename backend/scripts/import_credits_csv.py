from __future__ import annotations

import argparse
import csv
import ast
import json
import sqlite3
from pathlib import Path


def parse_json_list(value: str) -> list[dict]:
    value = (value or "").strip()
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        # credits.csv from Kaggle often uses Python-like dict strings with single quotes.
        # Example: "[{'cast_id': 14, 'character': 'Woody', ...}]"
        try:
            data = ast.literal_eval(value)
            return data if isinstance(data, list) else []
        except Exception:
            return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Kaggle credits.csv into SQLite (person, movie_cast, movie_crew).")
    parser.add_argument("--credits", required=True, help="Path to credits.csv from Kaggle The Movies Dataset")
    parser.add_argument("--sqlite", required=True, help="Path to SQLite database file (backend/data/movie_db.sqlite3)")
    parser.add_argument("--max-cast", type=int, default=20, help="Max cast members per movie to import (default: 20)")
    args = parser.parse_args()

    credits_path = Path(args.credits).expanduser().resolve()
    sqlite_path = Path(args.sqlite).expanduser().resolve()

    if not credits_path.exists():
        raise SystemExit(f"credits.csv not found: {credits_path}")
    if not sqlite_path.exists():
        raise SystemExit(f"sqlite db not found: {sqlite_path}")

    con = sqlite3.connect(sqlite_path)
    try:
        con.execute("PRAGMA foreign_keys = OFF;")

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS person (
              person_id INTEGER PRIMARY KEY,
              name TEXT NOT NULL
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS movie_cast (
              movie_id INTEGER NOT NULL,
              person_id INTEGER NOT NULL,
              character TEXT,
              cast_order INTEGER,
              PRIMARY KEY (movie_id, person_id),
              FOREIGN KEY (movie_id) REFERENCES movie(movie_id),
              FOREIGN KEY (person_id) REFERENCES person(person_id)
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS movie_crew (
              movie_id INTEGER NOT NULL,
              person_id INTEGER NOT NULL,
              job TEXT NOT NULL,
              PRIMARY KEY (movie_id, person_id, job),
              FOREIGN KEY (movie_id) REFERENCES movie(movie_id),
              FOREIGN KEY (person_id) REFERENCES person(person_id)
            );
            """
        )

        people_inserted = 0
        cast_rows = 0
        crew_rows = 0

        with credits_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                movie_id_raw = (row.get("id") or "").strip()
                if not movie_id_raw.isdigit():
                    continue
                movie_id = int(movie_id_raw)

                cast_list = parse_json_list(row.get("cast", ""))
                crew_list = parse_json_list(row.get("crew", ""))

                # Cast (limit to keep DB smaller and faster)
                for cast_item in cast_list[: max(0, args.max_cast)]:
                    pid = cast_item.get("id")
                    name = cast_item.get("name")
                    character = cast_item.get("character")
                    order = cast_item.get("order")

                    if not isinstance(pid, int) or not isinstance(name, str) or not name.strip():
                        continue

                    con.execute("INSERT OR IGNORE INTO person (person_id, name) VALUES (?, ?)", (pid, name.strip()))
                    con.execute(
                        "INSERT OR IGNORE INTO movie_cast (movie_id, person_id, character, cast_order) VALUES (?, ?, ?, ?)",
                        (movie_id, pid, character, order if isinstance(order, int) else None),
                    )
                    cast_rows += 1

                # Crew (we care most about Directors, but we can store all jobs)
                for crew_item in crew_list:
                    pid = crew_item.get("id")
                    name = crew_item.get("name")
                    job = crew_item.get("job")

                    if not isinstance(pid, int) or not isinstance(name, str) or not name.strip():
                        continue
                    if not isinstance(job, str) or not job.strip():
                        continue

                    con.execute("INSERT OR IGNORE INTO person (person_id, name) VALUES (?, ?)", (pid, name.strip()))
                    con.execute(
                        "INSERT OR IGNORE INTO movie_crew (movie_id, person_id, job) VALUES (?, ?, ?)",
                        (movie_id, pid, job.strip()),
                    )
                    crew_rows += 1

        # Simple indexes for speed
        con.execute("CREATE INDEX IF NOT EXISTS idx_person_name ON person(name);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_movie_cast_movie ON movie_cast(movie_id);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_movie_cast_person ON movie_cast(person_id);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_movie_crew_movie ON movie_crew(movie_id);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_movie_crew_person ON movie_crew(person_id);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_movie_crew_job ON movie_crew(job);")

        # If script is rerun, make sure we can add missing people rows too.
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_person_id_unique ON person(person_id);")

        con.commit()

        # Count people (optional)
        people_inserted = con.execute("SELECT COUNT(*) FROM person;").fetchone()[0]

        print("Import complete.")
        print("People:", people_inserted)
        print("Cast rows processed:", cast_rows)
        print("Crew rows processed:", crew_rows)
    finally:
        con.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

