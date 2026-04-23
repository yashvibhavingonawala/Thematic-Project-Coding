from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


def ensure_parent_dir(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)


def should_skip_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("--"):
        return True
    if stripped.upper().startswith("CREATE DATABASE"):
        return True
    if stripped.upper().startswith("USE "):
        return True
    return False


def normalize_statement(sql: str) -> str:
    s = sql.strip()

    # MySQL sometimes adds trailing spaces before semicolon.
    if s.endswith(";"):
        s = s[:-1].strip()

    upper = s.upper()

    # Some generated SQL rows contain NULL IDs for tables where the PK is NOT NULL.
    # Example: INSERT INTO production_country (country_id, country_name) VALUES (NULL, 'Namibia')
    # SQLite correctly rejects these; for this coursework dataset, skipping these broken rows is acceptable.
    if upper.startswith("INSERT INTO PRODUCTION_COUNTRY") and "VALUES (NULL" in upper:
        return ""
    if upper.startswith("INSERT INTO SPOKEN_LANGUAGE") and "VALUES (NULL" in upper:
        return ""

    # SQLite doesn't care about INT(11), BIGINT(20), VARCHAR(255) etc.
    # It also accepts FOREIGN KEY constraints in CREATE TABLE.
    # So we mostly keep SQL as-is and just remove MySQL-only statements (handled above).
    #
    # The dataset can contain duplicates; in SQLite we can safely ignore duplicates.
    # We convert:
    #   INSERT INTO ...
    # into:
    #   INSERT OR IGNORE INTO ...
    if upper.startswith("INSERT INTO "):
        s = "INSERT OR IGNORE INTO " + s[len("INSERT INTO ") :]
    return s


def execute_file(sql_path: Path, sqlite_path: Path) -> None:
    ensure_parent_dir(sqlite_path)

    con = sqlite3.connect(sqlite_path)
    try:
        # During import, rows may be inserted in an order that temporarily breaks FK rules.
        # We switch FK checks off while importing, then switch them on at the end.
        con.execute("PRAGMA foreign_keys = OFF;")

        statement_parts: list[str] = []
        executed = 0

        with sql_path.open("r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                if should_skip_line(raw_line):
                    continue

                statement_parts.append(raw_line)

                # We assume statements are terminated by ';' at end of line in your file.
                if raw_line.rstrip().endswith(";"):
                    stmt = normalize_statement("".join(statement_parts))
                    statement_parts = []

                    if not stmt:
                        continue

                    try:
                        con.execute(stmt)
                        executed += 1
                        if executed % 5000 == 0:
                            con.commit()
                            print(f"Executed {executed} statements...")
                    except sqlite3.Error as e:
                        # Print failing statement for debugging and stop.
                        print("\nSQLite error while executing statement:\n", stmt[:1000], file=sys.stderr)
                        raise

        con.commit()
        con.execute("PRAGMA foreign_keys = ON;")
        print(f"Done. Executed {executed} statements into {sqlite_path}")
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import MySQL .sql with INSERTs into a SQLite database.")
    parser.add_argument("--sql", required=True, help="Path to MySQL SQL file (movie_db_inserts.sql)")
    parser.add_argument("--sqlite", required=True, help="Path to output SQLite DB file (e.g. ./data/movie_db.sqlite3)")
    args = parser.parse_args()

    sql_path = Path(args.sql).expanduser().resolve()
    sqlite_path = Path(args.sqlite).expanduser().resolve()

    if not sql_path.exists():
        print(f"SQL file not found: {sql_path}", file=sys.stderr)
        return 2

    # Remove old db to avoid duplicate insert errors if re-running.
    if sqlite_path.exists():
        os.remove(sqlite_path)

    execute_file(sql_path, sqlite_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

