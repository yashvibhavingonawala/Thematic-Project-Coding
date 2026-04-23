from __future__ import annotations

import argparse
import json
import sqlite3
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError


TMDB_BASE = "https://image.tmdb.org/t/p"


@dataclass(frozen=True)
class DownloadResult:
    movie_id: int
    poster_path: str
    ok: bool
    status: int | None = None
    error: str | None = None


def tmdb_url(poster_path: str, size: str) -> str:
    # poster_path from Kaggle includes leading slash, e.g. "/abc.jpg"
    p = poster_path.strip()
    if not p.startswith("/"):
        p = "/" + p
    return f"{TMDB_BASE}/{size}{p}"


def safe_ext_from_poster_path(poster_path: str) -> str:
    p = (poster_path or "").lower()
    if p.endswith(".png"):
        return ".png"
    if p.endswith(".webp"):
        return ".webp"
    return ".jpg"


def fetch_bytes(url: str, timeout_s: int = 20) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "MovieCrewPosterDownloader/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return int(getattr(resp, "status", 200)), resp.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="Download TMDB posters locally for MovieCrew frontend.")
    parser.add_argument("--sqlite", required=True, help="Path to SQLite DB (backend/data/movie_db.sqlite3)")
    parser.add_argument(
        "--out",
        required=True,
        help="Output directory inside the frontend (e.g. Thematic project/assets/posters)",
    )
    parser.add_argument("--size", default="w342", help="TMDB size: w185, w342, w500, w780 (default: w342)")
    parser.add_argument("--delay-ms", type=int, default=120, help="Delay between downloads (default: 120ms)")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for testing (0 = all)")
    parser.add_argument("--worker", type=int, default=0, help="Worker index for parallel runs (default: 0)")
    parser.add_argument("--workers", type=int, default=1, help="Total workers for parallel runs (default: 1)")
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not sqlite_path.exists():
        raise SystemExit(f"SQLite DB not found: {sqlite_path}")

    con = sqlite3.connect(str(sqlite_path))
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT movie_id, poster_path
            FROM movie
            WHERE poster_path IS NOT NULL AND TRIM(poster_path) <> ''
            ORDER BY movie_id ASC
            """
        )
        rows = cur.fetchall()
    finally:
        con.close()

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    results: list[dict] = []
    downloaded = 0
    skipped = 0
    failed = 0

    workers = max(1, int(args.workers))
    worker = int(args.worker) % workers

    for i, (movie_id, poster_path) in enumerate(rows, start=1):
        # Parallelization: each worker handles a slice of the ordered list
        if (i - 1) % workers != worker:
            continue
        ext = safe_ext_from_poster_path(poster_path)
        out_path = out_dir / f"{int(movie_id)}{ext}"

        if out_path.exists() and out_path.stat().st_size > 0:
            skipped += 1
            continue

        url = tmdb_url(poster_path, args.size)

        try:
            status, data = fetch_bytes(url)
            # Some servers might return HTML on error; do a tiny sanity check.
            if not data or len(data) < 500:
                raise RuntimeError(f"Downloaded too-small file ({len(data)} bytes)")
            out_path.write_bytes(data)
            downloaded += 1
        except HTTPError as e:
            failed += 1
            results.append(DownloadResult(int(movie_id), str(poster_path), ok=False, status=int(e.code), error=str(e)).__dict__)
        except (URLError, Exception) as e:
            failed += 1
            results.append(DownloadResult(int(movie_id), str(poster_path), ok=False, status=None, error=str(e)).__dict__)

        if i % 100 == 0:
            print(
                f"[worker {worker+1}/{workers}] Processed {i}/{len(rows)} | "
                f"downloaded={downloaded} skipped={skipped} failed={failed}"
            )

        time.sleep(max(0, args.delay_ms) / 1000.0)

    report = {
        "sqlite": str(sqlite_path),
        "out": str(out_dir),
        "size": args.size,
        "total_rows": len(rows),
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "failures": results[:200],  # cap report
    }
    report_path = out_dir / "_download_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Done.")
    print(json.dumps({k: report[k] for k in ("total_rows", "downloaded", "skipped", "failed")}, indent=2))
    print("Report:", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

