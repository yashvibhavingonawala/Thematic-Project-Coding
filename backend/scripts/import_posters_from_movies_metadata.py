from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Import poster_path from movies_metadata.csv into SQLite movie table.")
    parser.add_argument("--metadata", required=True, help="Path to movies_metadata.csv")
    parser.add_argument("--sqlite", required=True, help="Path to SQLite database file")
    args = parser.parse_args()

    metadata_path = Path(args.metadata).expanduser().resolve()
    sqlite_path = Path(args.sqlite).expanduser().resolve()

    if not metadata_path.exists():
        raise SystemExit(f"movies_metadata.csv not found: {metadata_path}")
    if not sqlite_path.exists():
        raise SystemExit(f"sqlite db not found: {sqlite_path}")

    con = sqlite3.connect(sqlite_path)
    try:
        con.execute("PRAGMA foreign_keys = OFF;")

        cols = [r[1] for r in con.execute("PRAGMA table_info(movie)").fetchall()]
        if "poster_path" not in cols:
            con.execute("ALTER TABLE movie ADD COLUMN poster_path TEXT;")

        updated = 0
        seen = 0

        with metadata_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                seen += 1
                movie_id = (row.get("id") or "").strip()
                poster_path = (row.get("poster_path") or "").strip()

                if not movie_id.isdigit():
                    continue
                if not poster_path or poster_path == "null":
                    continue

                con.execute(
                    "UPDATE movie SET poster_path = ? WHERE movie_id = ?",
                    (poster_path, int(movie_id)),
                )
                updated += con.total_changes

                if seen % 10000 == 0:
                    con.commit()
                    print(f"Processed {seen} rows...")

        con.commit()
        posters_set = con.execute("SELECT COUNT(*) FROM movie WHERE poster_path IS NOT NULL AND poster_path != ''").fetchone()[0]
        print("Import complete.")
        print("Movies with posters:", posters_set)
    finally:
        con.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

