"""
Sync/refresh poster_path in SQLite using TMDB API.

Why:
- Your current `movie.poster_path` values (from older Kaggle dump) often 404 on TMDB now.
- This script queries TMDB Search API using (title + release_year) and updates `movie.poster_path`.

Requirements:
- Put your TMDB API key in `backend/.env` as TMDB_API_KEY=...

Usage:
  cd "Thematic project/backend"
  python3 scripts/sync_tmdb_poster_paths.py --sqlite "./data/movie_db.sqlite3" --limit 500

Then download posters locally:
  python3 scripts/download_posters_to_assets.py --sqlite "./data/movie_db.sqlite3" --out "../assets/posters" --size w342
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv


TMDB_SEARCH = "https://api.themoviedb.org/3/search/movie"


def _env(name: str) -> str:
    v = (os.getenv(name) or "").strip()
    if not v:
        raise SystemExit(f"Missing {name}. Set it in backend/.env (e.g. {name}=...)")
    return v


def _get_json(url: str, timeout_s: int = 20) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "MovieCrewPosterSync/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
    return json.loads(data.decode("utf-8"))


def _pick_best_result(results: list[dict], year: int | None) -> dict | None:
    if not results:
        return None
    if year is None:
        return results[0]

    # Prefer exact year match; otherwise closest year.
    best = None
    best_score = 10**9
    for r in results[:10]:
        rd = (r.get("release_date") or "").strip()
        ry = None
        if len(rd) >= 4 and rd[:4].isdigit():
            ry = int(rd[:4])
        if ry is None:
            continue
        score = 0 if ry == year else abs(ry - year) + 2
        if score < best_score:
            best_score = score
            best = r
    return best or results[0]


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Refresh poster_path using TMDB Search API.")
    ap.add_argument("--sqlite", required=True, help="Path to SQLite DB (backend/data/movie_db.sqlite3)")
    ap.add_argument("--limit", type=int, default=0, help="Max movies to process (0 = all)")
    ap.add_argument("--delay-ms", type=int, default=220, help="Delay between TMDB requests (default 220ms)")
    ap.add_argument("--only-missing", action="store_true", help="Only update movies with NULL/empty poster_path")
    ap.add_argument("--only-if-local-missing", action="store_true", help="Only update if assets/posters/<id>.jpg missing")
    ap.add_argument(
        "--assets-posters",
        default="../assets/posters",
        help="assets/posters directory (used with --only-if-local-missing)",
    )
    args = ap.parse_args()

    api_key = _env("TMDB_API_KEY")

    sqlite_path = Path(args.sqlite).expanduser().resolve()
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite DB not found: {sqlite_path}")

    posters_dir = Path(args.assets_posters).expanduser().resolve()

    con = sqlite3.connect(str(sqlite_path))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    where = []
    if args.only_missing:
        where.append("(poster_path IS NULL OR TRIM(poster_path)='')")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = cur.execute(
        f"""
        SELECT movie_id, title, release_year, poster_path
        FROM movie
        {where_sql}
        ORDER BY movie_id ASC
        """
    ).fetchall()

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    updated = 0
    not_found = 0
    skipped = 0

    for i, r in enumerate(rows, start=1):
        mid = int(r["movie_id"])
        title = (r["title"] or "").strip()
        year = int(r["release_year"]) if str(r["release_year"] or "").isdigit() else None

        if not title:
            skipped += 1
            continue

        if args.only_if_local_missing:
            local = posters_dir / f"{mid}.jpg"
            if local.exists() and local.stat().st_size > 0:
                skipped += 1
                continue

        q = {"api_key": api_key, "query": title}
        if year:
            q["year"] = str(year)
        url = TMDB_SEARCH + "?" + urllib.parse.urlencode(q)

        try:
            data = _get_json(url)
            results = data.get("results") or []
            best = _pick_best_result(results, year)
            new_path = (best or {}).get("poster_path") or ""
            if not new_path:
                not_found += 1
            else:
                # Store poster_path with leading slash, like TMDB.
                if not str(new_path).startswith("/"):
                    new_path = "/" + str(new_path)
                if new_path != (r["poster_path"] or ""):
                    cur.execute("UPDATE movie SET poster_path=? WHERE movie_id=?", (new_path, mid))
                    updated += 1
        except Exception:
            not_found += 1

        if i % 200 == 0:
            con.commit()
            print(f"Processed {i}/{len(rows)} | updated={updated} skipped={skipped} not_found={not_found}")

        time.sleep(max(0, args.delay_ms) / 1000.0)

    con.commit()
    con.close()

    print("Done.")
    print({"processed": len(rows), "updated": updated, "skipped": skipped, "not_found": not_found})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

